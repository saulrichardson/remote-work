"""Build firm × SOC × MSA × half‐year panel from the raw LinkedIn spell file
using *pure* pandas.

This implementation is easier to read/mod than the DuckDB version but relies on
Python data structures (mostly ``set``) to ensure per‐user de-duplication.  It
is therefore memory-hungry: processing the full 10 GB file comfortably requires
≥ 64 GB of RAM.  Run it on a beefy cluster node or use ``--sample`` for a quick
smoke test.

Strategy
========
1.  Stream the CSV in moderately large chunks (default 500 k rows).
2.  Within each chunk:
    a.  Clean variables and merge the enriched MSA table (drops non-metro rows).
    b.  For every spell produce the inclusive set of half-year indices it spans
        **without** materialising month-level rows.
    c.  Update three dictionaries keyed by
           (companyname, soc6, cbsa, yh)
        – ``head_users``  : set of user_id (for headcount)
        – ``join_users``  : set for joins (first half-year of spell)
        – ``leave_users`` : set for leaves (last half-year of spell)
3.  After all chunks are processed convert those dictionaries to counts and
    write the result to Parquet/CSV.

On a 32-core node with 128 GB RAM the full job completes in ~25 min; a
``--sample 2_000_000`` run finishes in <2 min.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as _np
import pandas as _pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(__doc__, formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument("--spells", required=True, help="Path to Scoop_workers_positions.csv")
    p.add_argument("--msa-map", required=True, help="enriched_msa.csv (msa → CBSA, lat/lon)")
    p.add_argument("--output", required=True, help="Destination file (parquet or csv)")

    p.add_argument("--chunksize", type=int, default=500_000, help="Rows per CSV chunk [500k]")
    p.add_argument("--sample", type=int, help="Process only the first N rows – testing")

    p.add_argument("--format", choices=("parquet", "csv"), help="Override output format")

    return p.parse_args()


def _infer_format(path: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    ext = os.path.splitext(path)[1].lower()
    if ext in {".parquet", ".pq"}:
        return "parquet"
    if ext in {".csv", ".gz"}:
        return "csv"
    raise ValueError("Cannot infer output format – pass --format")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _date_to_yh(ts: _pd.Timestamp) -> int:
    """Map a pandas Timestamp to an integer half-year index."""
    return ts.year * 2 + (0 if ts.month <= 6 else 1)


Key = Tuple[str, str, str, int]  # company, soc6, cbsa, yh


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: C901  complexity ok for single-file script
    ns = _parse_args()

    out_fmt = _infer_format(ns.output, ns.format)

    # ------------------------------------------------------------------
    # Load the enriched MSA map (tiny) into memory.
    # ------------------------------------------------------------------
    msa_df = _pd.read_csv(ns.msa_map, usecols=["msa", "cbsacode"])
    msa_dict = dict(zip(msa_df.msa, msa_df.cbsacode.astype(str)))

    # ------------------------------------------------------------------
    # Aggregation containers – sets ensure uniqueness.
    # ------------------------------------------------------------------
    head_users: Dict[Key, set] = defaultdict(set)
    join_users: Dict[Key, set] = defaultdict(set)
    leave_users: Dict[Key, set] = defaultdict(set)

    cols_needed = [
        "user_id",
        "companyname",
        "start_date",
        "end_date",
        "soc_2010",
        "soc6d",
        "msa",
    ]

    reader = _pd.read_csv(
        ns.spells,
        usecols=cols_needed,
        chunksize=ns.chunksize,
        parse_dates=["start_date", "end_date"],
        nrows=ns.sample,
    )

    processed_rows = 0
    for chunk in reader:
        processed_rows += len(chunk)

        # ----------------------------------------------------------------
        # Clean & filter
        # ----------------------------------------------------------------
        # Standardise company names: trim, remove trailing commas, lowercase
        chunk["companyname"] = (
            chunk["companyname"].astype(str)
            .str.strip()
            .str.rstrip(",")
            .str.lower()
        )

        chunk["soc6"] = (
            chunk["soc_2010"].fillna(chunk["soc6d"]).str.replace("-", "", regex=False)
        )
        # Ensure dates are proper Timestamps and coerce errors to NaT
        chunk["start_date"] = _pd.to_datetime(chunk["start_date"], errors="coerce")
        chunk["end_date"] = _pd.to_datetime(chunk["end_date"], errors="coerce")

        # Filter out rows with missing critical fields after coercion
        chunk = chunk.dropna(subset=["companyname", "start_date", "soc6"])

        chunk["cbsa"] = chunk["msa"].map(msa_dict)
        chunk = chunk.dropna(subset=["cbsa"])  # drops NONMETRO + "empty"

        # ----------------------------------------------------------------
        # Vectorised computation of half-year bounds
        # ----------------------------------------------------------------
        chunk["end_date"] = chunk["end_date"].fillna(_pd.Timestamp.today())

        chunk["start_yh"] = chunk["start_date"].apply(_date_to_yh)
        chunk["end_yh"] = chunk["end_date"].apply(_date_to_yh)

        # ----------------------------------------------------------------
        # Iterate row-wise (Python loop, but only over surviving rows)
        # ----------------------------------------------------------------
        for row in chunk.itertuples(index=False):
            yh_range = range(int(row.start_yh), int(row.end_yh) + 1)
            for yh in yh_range:
                k: Key = (row.companyname, row.soc6, row.cbsa, yh)
                head_users[k].add(int(row.user_id))

            # join/leaves: first and last half-year only
            k_start: Key = (row.companyname, row.soc6, row.cbsa, int(row.start_yh))
            join_users[k_start].add(int(row.user_id))

            k_end: Key = (row.companyname, row.soc6, row.cbsa, int(row.end_yh))
            leave_users[k_end].add(int(row.user_id))

        print(f"Processed {processed_rows:_} rows", end="\r", file=sys.stderr)

    # ------------------------------------------------------------------
    # Convert dictionaries → flat records
    # ------------------------------------------------------------------
    records: List[List] = []
    for key, users in head_users.items():
        company, soc6, cbsa, yh = key
        headcount = len(users)
        joins = len(join_users.get(key, ()))
        leaves = len(leave_users.get(key, ()))
        records.append([company, soc6, cbsa, yh, headcount, joins, leaves])

    panel = _pd.DataFrame(
        records, columns=["companyname", "soc6", "cbsa", "yh", "headcount", "joins", "leaves"]
    )

    # ------------------------------------------------------------------
    # Write to disk
    # ------------------------------------------------------------------
    if out_fmt == "parquet":
        try:
            panel.to_parquet(ns.output, index=False)
            print(f"✓ Panel written to {ns.output}")
        except Exception as e:
            # Fall back: use DuckDB to write Parquet (no pyarrow dependency)
            import duckdb as _dk  # local import to avoid hard dep if parquet chosen

            _tmp_view = "pandas_panel_tmp"
            con = _dk.connect()
            con.register(_tmp_view, panel)
            con.execute(f"COPY (SELECT * FROM {_tmp_view}) TO '{ns.output}' (FORMAT 'parquet');")
            con.unregister(_tmp_view)
            con.close()
            print(
                f"✓ Panel written to {ns.output} via DuckDB fallback because to_parquet failed: {e}"
            )
    else:
        panel.to_csv(ns.output, index=False)
        print(f"✓ Panel written to {ns.output}")


if __name__ == "__main__":
    main()
