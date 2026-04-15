#!/usr/bin/env python3
"""
Build firm-entry hires (first time a user joins a firm) with location at entry.

Purpose
-------
Create a clean hires dataset where each hire represents a user's first entry
into a firm, attributed to the CBSA (or 'remote') of that entry month. This
avoids counting internal SOC changes or intra-firm transfers as hires.

Outputs
-------
data/clean/firm_entry_hires.parquet
  - Columns: firm, yh, cbsa, is_remote, hires, new_location_entries

Definitions
-----------
- firm-entry hire: First observed start at a firm for a given user
- yh: half-year index = year*2 + (month>6)
- cbsa: mapped from MSA; 'remote' if MSA does not map
- is_remote: 1 if cbsa='remote' (unmapped MSA), else 0
- new_location_entries: first ever firm×cbsa entry observed in post-baseline
  period (yh >= 4040) — counts only when the firm's earliest hire in that
  CBSA occurs post-baseline.

Usage
-----
python py/build_firm_entry_hires.py \
    --spells   data/raw/Scoop_workers_positions.csv \
    --msa-map  data/clean/enriched_msa.csv      \
    --output   data/clean/firm_entry_hires.parquet

Notes
-----
- Mirrors companyname/MSA cleaning used in build_linkedin_panel_with_remote.py
- DuckDB implementation for speed and memory efficiency
- Provides --sample for quick validation
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import duckdb as _dk
except ModuleNotFoundError:
    print("ERROR: duckdb is required. pip install duckdb")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )

    p.add_argument("--spells", required=True, help="Path to Scoop_workers_positions.csv")
    p.add_argument("--msa-map", required=True, help="Path to enriched_msa.csv with msa→cbsa")
    p.add_argument(
        "--output",
        default=str(PROC / "firm_entry_hires.parquet"),
        help="Output file (parquet or csv; inferred by extension)",
    )
    p.add_argument("--threads", type=int, default=None, help="DuckDB threads")
    p.add_argument("--sample", type=int, default=None, help="Process only first N rows")
    p.add_argument("--temp-dir", help="DuckDB temp directory (PRAGMA temp_directory)")

    return p.parse_args()


def _infer_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".parquet", ".pq"}:
        return "parquet"
    if ext in {".csv", ".gz"}:
        return "csv"
    raise ValueError("Unsupported output extension; use .parquet or .csv")


def main() -> None:
    ns = _parse_args()
    out_fmt = _infer_format(ns.output)

    con = _dk.connect()

    if ns.threads:
        con.execute(f"PRAGMA threads={ns.threads};")

    tmp_dir = ns.temp_dir or os.environ.get("VAST") or os.environ.get("DUCKDB_TEMP_DIRECTORY")
    if tmp_dir:
        os.makedirs(tmp_dir, exist_ok=True)
        con.execute(f"PRAGMA temp_directory='{tmp_dir.replace("'", "''")}';")

    print("\n" + "=" * 70)
    print("Building firm-entry hires (first entry per user×firm)")
    print("=" * 70)

    # 1) Load MSA/C BSA mapping
    print("Loading MSA→CBSA mapping...")
    con.execute(
        f"""
        CREATE TEMP TABLE msa_map AS
        SELECT
            TRIM(msa) AS msa,
            CAST(cbsacode AS VARCHAR) AS cbsa
        FROM read_csv_auto('{ns.msa_map}', header=True)
        WHERE cbsacode IS NOT NULL
        """
    )

    # 2) Load spells (optionally sampled)
    limit_clause = "" if ns.sample is None else f"LIMIT {ns.sample}"
    print("Reading raw spells...")
    con.execute(
        f"""
        CREATE TEMP VIEW spells AS
        SELECT
            TRY_CAST(user_id AS BIGINT) AS user_id,
            lower(trim(regexp_replace(companyname, ',+$', ''))) AS firm,
            TRY_CAST(start_date AS DATE) AS start_date,
            TRY_CAST(end_date   AS DATE) AS end_date,
            msa
        FROM read_csv_auto(
            '{ns.spells}',
            header=true,
            strict_mode=false,
            all_varchar=true,
            ignore_errors=true,
            null_padding=true
        )
        WHERE companyname IS NOT NULL
          AND start_date IS NOT NULL
        {limit_clause};
        """
    )

    # 3) Map to CBSA and compute entry month
    print("Mapping MSA to CBSA and computing entry month...")
    con.execute(
        """
        CREATE TEMP VIEW entries_raw AS
        SELECT
            s.user_id,
            s.firm,
            date_trunc('month', s.start_date) AS start_m,
            CASE WHEN m.cbsa IS NOT NULL THEN m.cbsa ELSE 'remote' END AS cbsa,
            CASE WHEN m.cbsa IS NULL THEN 1 ELSE 0 END AS is_remote
        FROM spells s
        LEFT JOIN msa_map m USING (msa)
        WHERE s.user_id IS NOT NULL
    """
    )

    # 4) First firm entry per user (firm-entry hires)
    print("Identifying first firm entry per user...")
    con.execute(
        """
        CREATE TEMP VIEW firm_entry AS
        SELECT * FROM (
            SELECT
                user_id,
                firm,
                cbsa,
                is_remote,
                start_m,
                ((year(start_m) * 2) + (CASE WHEN month(start_m) > 6 THEN 1 ELSE 0 END)) AS yh,
                ROW_NUMBER() OVER (PARTITION BY firm, user_id ORDER BY start_m) AS rn
            FROM entries_raw
        )
        WHERE rn = 1
    """
    )

    # 5) Compute first-ever firm×cbsa hire timing to flag post-baseline new entries
    print("Flagging first post-baseline firm×CBSA entries...")
    con.execute(
        """
        -- First-ever observed yh per firm×cbsa among firm-entry hires
        CREATE TEMP VIEW cbsa_first_yh AS
        SELECT
            firm,
            cbsa,
            MIN(yh) AS first_yh
        FROM firm_entry
        GROUP BY firm, cbsa;

        -- Join back to flag if this row is the first post-baseline entry
        CREATE TEMP VIEW firm_entry_flagged AS
        SELECT
            e.firm,
            e.cbsa,
            e.is_remote,
            e.yh,
            e.user_id,
            CASE WHEN f.first_yh >= 4040 AND e.yh = f.first_yh THEN 1 ELSE 0 END AS first_post_baseline_entry
        FROM firm_entry e
        JOIN cbsa_first_yh f
          ON e.firm = f.firm AND e.cbsa = f.cbsa
    """
    )

    # 6) Aggregate to firm×yh×cbsa×is_remote
    print("Aggregating hires and new-location entries...")
    con.execute(
        """
        CREATE TEMP VIEW hires_agg AS
        SELECT
            firm,
            yh,
            cbsa,
            is_remote,
            COUNT(DISTINCT user_id) AS hires,
            -- Count first entries since baseline only for physical CBSAs
            SUM(CASE WHEN is_remote = 0 THEN first_post_baseline_entry ELSE 0 END) AS new_location_entries
        FROM firm_entry_flagged
        WHERE yh >= 4040
        GROUP BY 1,2,3,4
        ORDER BY firm, yh, cbsa
    """
    )

    # 7) Persist
    print("\nWriting output...")
    if out_fmt == "parquet":
        con.execute(f"COPY hires_agg TO '{ns.output}' (FORMAT 'parquet');")
    else:
        con.execute(f"COPY hires_agg TO '{ns.output}' (HEADER, DELIMITER ',');")

    # 8) Summary
    stats = con.execute(
        """
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT firm) AS firms,
            SUM(hires) AS total_hires,
            SUM(new_location_entries) AS first_entries,
            SUM(CASE WHEN cbsa='remote' THEN hires ELSE 0 END) AS remote_hires
        FROM hires_agg
        """
    ).fetchone()

    print("\nSummary:")
    print(f"  Rows: {stats[0]:,}")
    print(f"  Firms: {stats[1]:,}")
    print(f"  Total hires: {stats[2]:,}")
    print(f"  First entries since baseline: {stats[3]:,}")
    print(f"  Remote hires: {stats[4]:,}")

    print("\n" + "=" * 70)
    print(f"✓ Wrote firm-entry hires to {ns.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
