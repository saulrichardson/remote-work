#!/usr/bin/env python3
"""Compute firm × half-year location concentration (HHI) from the LinkedIn panel."""

from __future__ import annotations

import math
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
PANEL = PROC / "linkedin_panel.parquet"
OUTPUT = PROC / "firm_location_hhi.csv"


QUERY = """
WITH base AS (
    SELECT lower(companyname) AS companyname_lower,
           CAST(yh AS INTEGER) AS yh_int,
           cbsa,
           COALESCE(cbsa_from_lookup, 0) AS cbsa_from_lookup_flag,
           SUM(headcount) AS headcount
    FROM read_parquet('{panel}')
    WHERE headcount IS NOT NULL AND headcount > 0 AND cbsa IS NOT NULL
    GROUP BY 1,2,3,4
), totals AS (
    SELECT companyname_lower,
           yh_int,
           SUM(headcount) AS total_headcount_all,
           SUM(CASE WHEN cbsa_from_lookup_flag = 0 THEN headcount ELSE 0 END) AS total_headcount_original
    FROM base
    GROUP BY 1,2
)
SELECT
    b.companyname_lower,
    b.yh_int,
    COUNT(*) FILTER (WHERE b.headcount > 0) AS n_cbsas,
    SUM(CASE WHEN t.total_headcount_all > 0 THEN POWER(b.headcount::DOUBLE / t.total_headcount_all, 2) END) AS hhi,
    t.total_headcount_all AS total_headcount,
    COUNT(*) FILTER (WHERE b.headcount > 0 AND b.cbsa_from_lookup_flag = 0) AS n_cbsas_original,
    SUM(CASE WHEN b.cbsa_from_lookup_flag = 0 AND t.total_headcount_original > 0 THEN POWER(b.headcount::DOUBLE / t.total_headcount_original, 2) END) AS hhi_original,
    t.total_headcount_original AS total_headcount_original,
    SUM(CASE WHEN b.cbsa_from_lookup_flag = 1 THEN b.headcount ELSE 0 END) AS headcount_from_lookup
FROM base b
JOIN totals t USING (companyname_lower, yh_int)
GROUP BY 1,2, t.total_headcount_all, t.total_headcount_original
"""


def main() -> None:
    if not PANEL.exists():
        raise FileNotFoundError(f"LinkedIn panel missing at {PANEL}")

    con = duckdb.connect()
    try:
        df = con.execute(QUERY.format(panel=PANEL.as_posix())).fetchdf()
    finally:
        con.close()

    if df.empty:
        raise RuntimeError("No HHI rows were produced; check upstream data.")

    df["hhi_10000"] = df["hhi"] * 10000
    df["effective_locations"] = df["hhi"].map(lambda x: (1.0 / x) if x and not math.isclose(x, 0.0) else pd.NA)
    df["hhi_original_10000"] = df["hhi_original"].map(lambda x: x * 10000 if pd.notna(x) else pd.NA)
    df["effective_locations_original"] = df["hhi_original"].map(lambda x: (1.0 / x) if pd.notna(x) and not math.isclose(x, 0.0) else pd.NA)
    df["share_headcount_from_lookup"] = df.apply(
        lambda r: (r["headcount_from_lookup"] / r["total_headcount"])
        if r["total_headcount"] and not math.isclose(r["total_headcount"], 0.0)
        else pd.NA,
        axis=1,
    )

    df = df[
        [
            "companyname_lower",
            "yh_int",
            "n_cbsas",
            "n_cbsas_original",
            "total_headcount",
            "total_headcount_original",
            "headcount_from_lookup",
            "share_headcount_from_lookup",
            "hhi",
            "hhi_10000",
            "effective_locations",
            "hhi_original",
            "hhi_original_10000",
            "effective_locations_original",
        ]
    ].sort_values(["companyname_lower", "yh_int"]).reset_index(drop=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)

    print("Saved firm-level location HHI:")
    print(f"  Rows: {len(df):,}")
    print(f"  Firms: {df['companyname_lower'].nunique():,}")
    print(df[["hhi", "effective_locations"]].describe())


if __name__ == "__main__":
    main()
