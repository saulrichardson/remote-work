"""Build firm-level teleworkability scores using Python instead of the
previous Stata implementation (``src/build_firm_teleworkable_scores.do``).

The logic follows the original .do script as closely as possible while
streaming the 10 GB *Scoop_workers_positions.csv* in pandas chunks so the
process fits comfortably in memory.

Steps
-----
1.  Read *role × ONET* lookup (``rolek1000_onet_cw.csv``) and keep only
    ONET codes ending in ``.00``.  Derive ``soc_new`` = first seven
    characters (e.g. ``"13-2011"``).
2.  Read ONET tele-workability scores (``occupations_workathome.csv``),
    keep only ``.00`` rows, derive the same ``soc_new`` and merge onto the
    role lookup to obtain a mapping ``role_k1000 → teleworkable``.
3.  Stream the spell CSV, keeping only the columns actually needed
    (``companyname``, ``role_k1000``, ``start_date``, ``end_date``).
    For every row that
        • has a non-missing role with a teleworkable score,
        • satisfies the two-year window 2018-01-01 – 2019-12-31
          (same logic as in the .do file),
    we accumulate *sum(tele)* and *count* per company.
4.  Compute the company-level mean and write
    ``data/cleaned/scoop_firm_tele_2.csv`` (or .parquet).

Compared to the Stata version this implementation avoids brittle CSV
parsing issues and re-uses the shared company-name normalisation logic.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from datetime import datetime as _dt
from pathlib import Path
from typing import Dict, Tuple

import pandas as _pd

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("Build firm-level teleworkability scores")

    p.add_argument(
        "--roles",
        default="data/raw/rolek1000_onet_cw.csv",
        help="role_k1000 → ONET mapping (CSV)",
    )
    p.add_argument(
        "--telework",
        default="data/raw/occupations_workathome.csv",
        help="ONET teleworkability scores (CSV)",
    )
    p.add_argument(
        "--spells",
        default="data/raw/Scoop_workers_positions.csv",
        help="LinkedIn spell dump",
    )
    p.add_argument(
        "--output",
        default="data/cleaned/scoop_firm_tele_2.csv",
        help="Destination (CSV or Parquet)",
    )
    p.add_argument("--chunksize", type=int, default=500_000, help="Spell CSV chunk size")
    p.add_argument("--sample", type=int, help="Only process first N rows – debugging")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _standardise_company(name: str) -> str:
    """Trim, remove trailing commas, lower-case."""
    return name.strip().rstrip(",").lower()


# ---------------------------------------------------------------------------
# Role-level teleworkability
# ---------------------------------------------------------------------------


def _build_role_lookup(role_csv: str, tele_csv: str) -> _pd.Series:
    """Return Series mapping role_k1000 → teleworkable (mean)."""

    roles = _pd.read_csv(role_csv, dtype=str, usecols=["role_k1000", "onet_code"])
    # keep only codes ending .00 and derive soc_new (first 7 chars)
    roles = roles[roles["onet_code"].str.endswith(".00", na=False)].copy()
    roles["soc_new"] = roles["onet_code"].str[:7]

    tele = _pd.read_csv(tele_csv, dtype=str, usecols=["onetsoccode", "teleworkable"])
    tele = tele[tele["onetsoccode"].str.endswith(".00", na=False)].copy()
    tele["soc_new"] = tele["onetsoccode"].str[:7]
    tele["teleworkable"] = _pd.to_numeric(tele["teleworkable"], errors="coerce")

    merged = roles.merge(tele[["soc_new", "teleworkable"]], on="soc_new", how="inner")

    role_scores = (
        merged.groupby("role_k1000", dropna=False)["teleworkable"].mean().dropna()
    )
    # Drop unwanted roles matching the original .do logic
    role_scores = role_scores.drop(index=["10.0", "7.0"], errors="ignore")
    return role_scores


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: C901
    ns = _parse_args()

    # 1) build role → teleworkable lookup
    role_scores = _build_role_lookup(ns.roles, ns.telework)

    # 2) stream spells and accumulate per-company sums
    cols = ["companyname", "role_k1000", "start_date", "end_date"]
    reader = _pd.read_csv(
        ns.spells,
        usecols=cols,
        chunksize=ns.chunksize,
        nrows=ns.sample,
        dtype={"companyname": str, "role_k1000": str},
        parse_dates=["start_date", "end_date"],
    )

    # aggregation dicts
    sums: Dict[str, Tuple[float, int]] = defaultdict(lambda: [0.0, 0])

    # window boundaries
    start_cutoff = _dt(2017, 12, 31)
    end_cutoff = _dt(2019, 12, 31)

    for chunk in reader:
        # basic cleaning
        chunk["companyname"] = chunk["companyname"].fillna("").map(_standardise_company)

        # map teleworkable via role_k1000; drop if role missing or not mapped
        chunk["tele"] = chunk["role_k1000"].map(role_scores)
        chunk = chunk.dropna(subset=["tele", "companyname"])

        if chunk.empty:
            continue

        # date filtering
        chunk["start_date"] = _pd.to_datetime(chunk["start_date"], errors="coerce")
        chunk["end_date"] = _pd.to_datetime(chunk["end_date"], errors="coerce")
        chunk["end_date"].fillna(chunk["start_date"], inplace=True)

        mask = (chunk["end_date"] >= start_cutoff) & (chunk["start_date"] <= end_cutoff)
        chunk = chunk.loc[mask]

        for comp, sub in chunk.groupby("companyname", sort=False):
            sums[comp][0] += sub["tele"].sum()
            sums[comp][1] += len(sub)

    # build final DataFrame
    records = [
        (comp, total / cnt) for comp, (total, cnt) in sums.items() if cnt > 0
    ]

    out_df = _pd.DataFrame(records, columns=["companyname", "teleworkable"])

    # 3) drop unwanted roles at the *role level* already removed by lookup; we
    # keep the company-level DataFrame as is.

    # 4) output
    out_path = Path(ns.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() in {".parquet", ".pq"}:
        out_df.to_parquet(out_path, index=False)
    else:
        out_df.to_csv(out_path, index=False)

    print(f"✓ Firm teleworkability written to {out_path}  (n={len(out_df):,})")


if __name__ == "__main__":
    main()
