"""Build firm × SOC × MSA × half-year panel INCLUDING REMOTE WORKERS.

This is a modified version of build_linkedin_panel_duckdb.py that INCLUDES
workers with empty/missing MSA values (remote workers), who comprise ~31% 
of the raw data but were previously excluded.

Key changes from original:
1. Keeps rows where MSA doesn't map to CBSA (remote workers)
2. Adds 'is_remote' flag to identify these workers
3. Uses 'remote' as cbsa value when MSA is empty/unmapped

This enables the three-way classification analysis:
- Legacy MSA hires (traditional office locations)  
- New MSA hires (new physical locations)
- Remote hires (no MSA designation)

Usage:
------
python py/build_linkedin_panel_with_remote.py \
       --spells     data/raw/Scoop_workers_positions.csv \
       --msa-map    data/clean/enriched_msa.csv      \
       --output     data/clean/linkedin_panel_with_remote.parquet

Output adds these columns vs original:
- is_remote: 1 if worker has no MSA/CBSA, 0 otherwise
- cbsa: 'remote' for remote workers, actual CBSA code otherwise
"""

from __future__ import annotations

import argparse
import datetime as _dt
import math
import os
import sys
from pathlib import Path

try:
    import duckdb as _dk
    _HAVE_DUCKDB = True
except ModuleNotFoundError:
    _HAVE_DUCKDB = False

import pandas as _pd
import numpy as _np

ROOT = Path(__file__).resolve().parent.parent
USER_CBSA_CSV = ROOT / "data" / "processed" / "user_location_lookup.csv"
VALID_LOOKUP_MATCHES = (
    "alias",
    "principal_city",
    "principal_city_altstate",
    "principal_city_state_guess",
    "nearest_cbsa_state",
    "nearest_cbsa_cross_state",
)

LOOKUP_PRIORITY_SQL = "CASE match_quality " \
    "WHEN 'alias' THEN 1 " \
    "WHEN 'principal_city' THEN 2 " \
    "WHEN 'principal_city_altstate' THEN 3 " \
    "WHEN 'principal_city_state_guess' THEN 4 " \
    "WHEN 'nearest_cbsa_state' THEN 5 " \
    "WHEN 'nearest_cbsa_cross_state' THEN 6 " \
    "ELSE 9 END"

LOOKUP_PRIORITY = {
    "alias": 1,
    "principal_city": 2,
    "principal_city_altstate": 3,
    "principal_city_state_guess": 4,
    "nearest_cbsa_state": 5,
    "nearest_cbsa_cross_state": 6,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(__doc__, formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument("--spells", required=True, help="Path to Scoop_workers_positions.csv")
    p.add_argument(
        "--msa-map",
        required=True,
        help="CSV with columns: msa,cbsacode,lat,lon (enriched_msa.csv)",
    )
    p.add_argument(
        "--output",
        required=True,
        help="Destination file (extension determines format unless --format given)",
    )
    p.add_argument(
        "--threads",
        type=int,
        default=None,
        help="DuckDB threads (default: all cores)",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Load only the first N rows – for quick testing",
    )
    p.add_argument(
        "--format",
        choices=("parquet", "csv"),
        help="Force output format (otherwise derived from --output extension)",
    )
    p.add_argument(
        "--temp-dir",
        help="Directory for DuckDB temporary spill files (overrides PRAGMA temp_directory).",
    )

    return p.parse_args()


def _infer_output_format(path: str, explicit: str | None) -> str:
    if explicit:
        return explicit.lower()
    ext = os.path.splitext(path)[1].lower()
    if ext in {".parquet", ".pq"}:
        return "parquet"
    if ext in {".csv", ".gz"}:
        return "csv"
    raise ValueError("Cannot infer output format; please pass --format")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: C901
    ns = _parse_args()
    out_format = _infer_output_format(ns.output, ns.format)

    print("\n" + "="*70)
    print("Building LinkedIn Panel WITH REMOTE WORKERS")
    print("="*70)
    print("This version INCLUDES workers without MSA designations (remote)")
    print("="*70 + "\n")

    # ------------------------------------------------------------------
    # Preferred path: DuckDB is available.
    # ------------------------------------------------------------------
    if _HAVE_DUCKDB:
        con = _dk.connect()

        # Configure temp spill directory to avoid hitting home quota.
        tmp_dir = ns.temp_dir or os.environ.get("VAST") or os.environ.get("DUCKDB_TEMP_DIRECTORY")
        if tmp_dir:
            # Ensure directory exists; DuckDB will error otherwise.
            if not os.path.isdir(tmp_dir):
                os.makedirs(tmp_dir, exist_ok=True)
            safe_tmp = tmp_dir.replace("'", "''")
            con.execute(f"PRAGMA temp_directory='{safe_tmp}';")

        if ns.threads:
            con.execute(f"PRAGMA threads={ns.threads};")

        # 1) MSA map
        print("Loading MSA to CBSA mapping...")
        con.execute(
            f"""
            CREATE TEMP TABLE msa_map AS
            SELECT
                TRIM(msa) AS msa,
                CAST(cbsacode AS VARCHAR) AS cbsa,
                CAST(lat AS DOUBLE) AS lat,
                CAST(lon AS DOUBLE) AS lon
            FROM read_csv_auto('{ns.msa_map}', header=True);
            """
        )

        limit_clause = "" if ns.sample is None else f"LIMIT {ns.sample}"

        if not USER_CBSA_CSV.exists():
            raise FileNotFoundError(USER_CBSA_CSV)

        priority_case = LOOKUP_PRIORITY_SQL
        con.execute(
            f"""
            CREATE TEMP TABLE user_cbsa AS
            WITH raw AS (
                SELECT
                    CAST(user_id AS BIGINT) AS user_id,
                    cbsa,
                    match_quality,
                    ROW_NUMBER() OVER (
                        PARTITION BY CAST(user_id AS BIGINT)
                        ORDER BY {priority_case}
                    ) AS rn
                FROM read_csv_auto(
                    '{USER_CBSA_CSV.as_posix()}',
                    header=true,
                    all_varchar=true,
                    ignore_errors=true
                )
                WHERE cbsa IS NOT NULL
                  AND match_quality IN ({", ".join(repr(m) for m in VALID_LOOKUP_MATCHES)})
            )
            SELECT user_id, cbsa
            FROM raw
            WHERE rn = 1;
            """
        )

        print("Reading spell data...")
        con.execute(
            f"""
            CREATE TEMP VIEW spells AS
            SELECT
                CAST(user_id AS BIGINT)       AS user_id,
                companyname,
                TRY_CAST(start_date AS DATE)      AS start_date,
                TRY_CAST(end_date   AS DATE)      AS end_date,
                soc_2010,
                soc6d,
                msa
            FROM read_csv_auto(
                '{ns.spells}',
                header=true,
                strict_mode=false,
                all_varchar=true,
                ignore_errors=true,
                null_padding=true
            )
            {limit_clause};
            """
        )

        # 3) Clean + merge MSA + SOC
        # KEY CHANGE: Keep ALL rows, flag remote workers
        print("Processing spells and identifying remote workers...")
        con.execute(
            """
            CREATE TEMP VIEW spells2 AS
            SELECT
                s.user_id,
                lower(trim(regexp_replace(s.companyname, ',+$', ''))) AS companyname,
                regexp_replace(COALESCE(s.soc_2010, s.soc6d), '-', '', 'g') AS soc6,
                date_trunc('month', s.start_date) AS start_m,
                date_trunc('month', COALESCE(s.end_date, current_date)) AS end_m,
                CASE
                    WHEN m.cbsa IS NOT NULL THEN m.cbsa
                    WHEN uc.cbsa IS NOT NULL THEN uc.cbsa
                    ELSE 'remote'
                END AS cbsa,
                CASE
                    WHEN m.cbsa IS NULL AND uc.cbsa IS NOT NULL THEN 1
                    ELSE 0
                END AS cbsa_from_lookup,
                CASE
                    WHEN m.cbsa IS NULL AND uc.cbsa IS NULL THEN 1
                    ELSE 0
                END AS is_remote,
                m.lat,
                m.lon
            FROM spells AS s
            LEFT JOIN msa_map AS m USING (msa)
            LEFT JOIN user_cbsa AS uc USING (user_id)
            WHERE s.companyname IS NOT NULL
              AND s.start_date IS NOT NULL
              AND COALESCE(s.soc_2010, s.soc6d) IS NOT NULL;
            """
        )

        # Quick stats on remote workers
        print("\nChecking remote worker statistics...")
        stats = con.execute("""
            SELECT 
                COUNT(*) as total_spells,
                SUM(is_remote) as remote_spells,
                ROUND(100.0 * SUM(is_remote) / COUNT(*), 2) as pct_remote
            FROM spells2;
        """).fetchone()
        
        print(f"  Total spells: {stats[0]:,}")
        print(f"  Remote spells: {stats[1]:,} ({stats[2]}%)")

        # 4) Month expansion + flags
        print("\nExpanding to monthly observations...")
        con.execute(
            """
            CREATE TEMP VIEW month_expanded AS
            SELECT
                user_id,
                companyname,
                soc6,
                cbsa,
                cbsa_from_lookup,
                is_remote,
                lat,
                lon,
                mon,
                (mon = start_m)::INTEGER AS join_flag,
                (mon = end_m)::INTEGER   AS leave_flag
            FROM spells2
            JOIN generate_series(start_m, end_m, INTERVAL '1 month') AS gen(mon) ON TRUE;
            """
        )

        # 5) Half-year aggregation
        print("Aggregating to half-year frequency...")
        con.execute(
            """
            CREATE TEMP VIEW half_year AS
            SELECT
                companyname,
                soc6,
                cbsa,
                MAX(cbsa_from_lookup) AS cbsa_from_lookup,
                MAX(is_remote) AS is_remote,
                ((year(mon) * 2) + (CASE WHEN month(mon) > 6 THEN 1 ELSE 0 END)) AS yh,
                ANY_VALUE(lat) AS lat,
                ANY_VALUE(lon) AS lon,
                COUNT(DISTINCT user_id) AS headcount,
                COUNT(DISTINCT CASE WHEN join_flag = 1  THEN user_id END) AS joins,
                COUNT(DISTINCT CASE WHEN leave_flag = 1 THEN user_id END) AS leaves
            FROM month_expanded
            GROUP BY 1,2,3,6;
            """
        )

        # Get final statistics
        final_stats = con.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT companyname) as n_firms,
                COUNT(DISTINCT CASE WHEN is_remote = 1 THEN companyname END) as firms_with_remote,
                SUM(CASE WHEN is_remote = 1 THEN headcount ELSE 0 END) as remote_headcount,
                SUM(headcount) as total_headcount,
                ROUND(100.0 * SUM(CASE WHEN is_remote = 1 THEN headcount ELSE 0 END) / SUM(headcount), 2) as pct_remote_headcount
            FROM half_year;
        """).fetchone()

        print(f"\nFinal panel statistics:")
        print(f"  Total rows: {final_stats[0]:,}")
        print(f"  Total firms: {final_stats[1]:,}")
        print(f"  Firms with remote workers: {final_stats[2]:,}")
        print(f"  Remote headcount: {final_stats[3]:,} / {final_stats[4]:,} ({final_stats[5]}%)")

        # 6) Persist
        print(f"\nWriting to {ns.output}...")
        if out_format == "parquet":
            con.execute(f"COPY half_year TO '{ns.output}' (FORMAT 'parquet');")
        else:
            con.execute(f"COPY half_year TO '{ns.output}' (HEADER, DELIMITER ',');")

        print(f"✓ Panel with remote workers written to {ns.output}")
        return

    # ------------------------------------------------------------------
    # Fallback path: DuckDB is unavailable (pandas implementation)
    # ------------------------------------------------------------------

    if ns.sample is None:
        sys.exit(
            "duckdb module not found and no --sample specified. Either install"
            " duckdb or run the script with --sample <N> to build a small test"
            " extract with pandas."
        )

    print("duckdb not available → falling back to pandas for a sample run", file=sys.stderr)

    # 1) Load MSA map into pandas
    msa_df = _pd.read_csv(ns.msa_map, usecols=["msa", "cbsacode", "lat", "lon"])
    
    # 2) Read sample rows from spells
    spell_df = _pd.read_csv(
        ns.spells,
        nrows=ns.sample,
        usecols=[
            "user_id",
            "companyname",
            "start_date",
            "end_date",
            "soc_2010",
            "soc6d",
            "msa",
        ],
        parse_dates=["start_date", "end_date"],
    )

    # 3) Pre-clean
    spell_df = spell_df.dropna(subset=["companyname", "start_date"])
    spell_df["soc6"] = (
        spell_df["soc_2010"].fillna(spell_df["soc6d"]).str.replace("-", "", regex=False)
    )
    spell_df = spell_df.dropna(subset=["soc6"])

    msa_df = msa_df.rename(columns={"cbsacode": "cbsa_map"})
    spell_df = spell_df.merge(msa_df, on="msa", how="left")

    if USER_CBSA_CSV.exists():
        lookup_df = _pd.read_csv(
            USER_CBSA_CSV,
            usecols=["user_id", "cbsa", "match_quality"],
        )
        lookup_df = lookup_df[lookup_df["match_quality"].isin(VALID_LOOKUP_MATCHES)].copy()
        lookup_df["priority"] = lookup_df["match_quality"].map(LOOKUP_PRIORITY)
        lookup_df = (
            lookup_df.sort_values(["priority"])
            .drop_duplicates("user_id", keep="first")
            .rename(columns={"cbsa": "cbsa_lookup"})
        )
        spell_df = spell_df.merge(lookup_df[["user_id", "cbsa_lookup"]], on="user_id", how="left")
    else:
        spell_df["cbsa_lookup"] = _pd.NA

    spell_df["cbsa_from_lookup"] = (
        spell_df["cbsa_map"].isna() & spell_df["cbsa_lookup"].notna()
    ).astype("int8")
    spell_df["cbsa"] = spell_df["cbsa_map"].fillna(spell_df["cbsa_lookup"])
    spell_df["is_remote"] = spell_df["cbsa"].isna().astype(int)
    spell_df["cbsa"] = spell_df["cbsa"].fillna("remote")

    print(f"\nRemote workers: {spell_df['is_remote'].sum()} / {len(spell_df)} spells")

    # 4) Month expansion in pandas
    def _expand_months(row: _pd.Series) -> _pd.DataFrame:
        start = row.start_date.to_period("M")
        end = (row.end_date if _pd.notna(row.end_date) else _pd.Timestamp.today()).to_period("M")
        months = _pd.period_range(start, end, freq="M")
        df = _pd.DataFrame({"mon": months.to_timestamp(), "join_flag": 0, "leave_flag": 0})
        df.loc[0, "join_flag"] = 1
        df.loc[len(df) - 1, "leave_flag"] = 1
        for col in ["user_id", "companyname", "soc6", "cbsa", "cbsa_from_lookup", "is_remote", "lat", "lon"]:
            df[col] = row[col]
        return df

    expanded = _pd.concat((_expand_months(r) for _, r in spell_df.iterrows()), ignore_index=True)

    # 5) Half-year aggregation
    expanded["year"] = expanded["mon"].dt.year
    expanded["half"] = (expanded["mon"].dt.month > 6).astype(int)
    expanded["yh"] = expanded["year"] * 2 + expanded["half"]

    grouped = (
        expanded.groupby(["companyname", "soc6", "cbsa", "cbsa_from_lookup", "is_remote", "yh"])
        .agg(
            headcount=("user_id", "nunique"),
            joins=("join_flag", "sum"),
            leaves=("leave_flag", "sum"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            cbsa_from_lookup=("cbsa_from_lookup", "max"),
        )
        .reset_index()
    )

    # 6) Output
    if out_format == "parquet":
        grouped.to_parquet(ns.output, index=False)
    else:
        grouped.to_csv(ns.output, index=False)

    print(f"✓ Panel sample with remote workers written to {ns.output} using pandas")


if __name__ == "__main__":
    main()
