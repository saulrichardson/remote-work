#!/usr/bin/env python3
"""Build a firm × half‑year panel with demographic hiring outcomes.

This script keeps the remote/startup scaling framework but augments it with
gender and age composition measures at the firm level. It intentionally lives
separately from the existing panel builders to avoid changing their behaviour.

Pipeline (DuckDB path, preferred on full data):
  1) Read the raw LinkedIn spell dump (Scoop_workers_positions.csv).
  2) Join user attributes (gender, approx_age_2020) from data/clean/user_attributes.csv.
  3) Map MSA → CBSA (enriched_msa.csv) and fall back to the user-level lookup
     (user_location_lookup.csv) as in the core builder.
  4) Expand spells to months, flag joins/leaves, then collapse to half‑year with
     gender counts and age means.
  5) Export a slim CSV (and Parquet) keyed by companyname,yh.
  6) Merge the demographics onto the existing firm_panel.dta to retain the
     remote/startup/instrument variables, writing firm_panel_demographics.(csv|dta).

Outputs
-------
  data/clean/firm_demographics_panel.csv          (raw demography aggregates)
  data/clean/firm_demographics_panel.parquet      (same, columnar)
  data/clean/firm_panel_demographics.csv          (demography merged onto firm_panel)
  data/clean/firm_panel_demographics.dta

Usage (full run):
  python src/py/build_firm_demographics_panel.py

Debug / sample run:
  python src/py/build_firm_demographics_panel.py --sample 100000

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

from project_paths import DATA_CLEAN, DATA_RAW, ensure_dir


DEFAULT_SPELLS = DATA_RAW / "Scoop_workers_positions.csv"
DEFAULT_MSA_MAP = DATA_CLEAN / "enriched_msa.csv"
DEFAULT_USER_CBSA = DATA_CLEAN / "user_location_lookup.csv"
DEFAULT_USER_ATTR = DATA_CLEAN / "user_attributes.csv"

OUT_DEMO_CSV = DATA_CLEAN / "firm_demographics_panel.csv"
OUT_DEMO_PARQUET = DATA_CLEAN / "firm_demographics_panel.parquet"
OUT_MERGED_CSV = DATA_CLEAN / "firm_panel_demographics.csv"
OUT_MERGED_DTA = DATA_CLEAN / "firm_panel_demographics.dta"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spells", default=DEFAULT_SPELLS, type=Path, help="Path to Scoop_workers_positions.csv")
    p.add_argument("--msa-map", default=DEFAULT_MSA_MAP, type=Path, help="Path to enriched_msa.csv")
    p.add_argument("--user-cbsa", default=DEFAULT_USER_CBSA, type=Path, help="Path to user_location_lookup.csv")
    p.add_argument("--user-attr", default=DEFAULT_USER_ATTR, type=Path, help="Path to user_attributes.csv")
    p.add_argument("--temp-dir", type=Path, help="Optional DuckDB temp directory (spills)")
    p.add_argument("--threads", type=int, help="DuckDB threads (default: all cores)")
    p.add_argument("--sample", type=int, help="Limit rows for a quick sample run")
    return p.parse_args()


def build_demography(ns: argparse.Namespace) -> None:
    # Ensure outputs
    ensure_dir(OUT_DEMO_CSV.parent)

    con = duckdb.connect()

    if ns.temp_dir:
        ns.temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"PRAGMA temp_directory='{ns.temp_dir.resolve()}'")
    if ns.threads:
        con.execute(f"PRAGMA threads={ns.threads}")

    # Register input paths
    spells_path = ns.spells.resolve()
    msa_path = ns.msa_map.resolve()
    cbsa_path = ns.user_cbsa.resolve()
    attr_path = ns.user_attr.resolve()

    if not spells_path.exists():
        raise FileNotFoundError(spells_path)
    for p in (msa_path, cbsa_path, attr_path):
        if not p.exists():
            raise FileNotFoundError(p)

    limit_clause = "" if ns.sample is None else f"LIMIT {ns.sample}"

    # ------------------------------------------------------------------
    # Load helper tables
    # ------------------------------------------------------------------
    con.execute(
        f"""
        CREATE TEMP TABLE msa_map AS
        SELECT TRIM(msa) AS msa,
               CAST(cbsacode AS VARCHAR) AS cbsa,
               CAST(lat AS DOUBLE) AS lat,
               CAST(lon AS DOUBLE) AS lon
        FROM read_csv_auto('{msa_path}', header=True);
        """
    )

    con.execute(
        f"""
        CREATE TEMP TABLE user_cbsa AS
        SELECT user_id::BIGINT AS user_id,
               cbsa,
               latitude AS lat,
               longitude AS lon,
               match_quality
        FROM read_csv_auto('{cbsa_path}', header=True);
        """
    )

    con.execute(
        f"""
        CREATE TEMP TABLE user_attr AS
        SELECT user_id::BIGINT AS user_id,
               gender_category,
               gender_confident,
               approx_age_2020
        FROM read_csv_auto('{attr_path}', header=True);
        """
    )

    # ------------------------------------------------------------------
    # Raw spells → cleaned subset with MSA mapping + demographics
    # ------------------------------------------------------------------
    con.execute(
        f"""
        CREATE TEMP TABLE spells AS
        SELECT
            CAST(user_id AS BIGINT) AS user_id,
            lower(trim(regexp_replace(companyname, ',+$', ''))) AS companyname,
            regexp_replace(COALESCE(soc_2010, soc6d), '-', '', 'g') AS soc6,
            CAST(start_date AS DATE) AS start_date,
            COALESCE(CAST(end_date AS DATE), current_date) AS end_date,
            msa
        FROM read_csv_auto(
            '{spells_path}',
            header=True,
            dateformat='%Y-%m-%d',
            all_varchar=true,
            ignore_errors=true,
            strict_mode=false
        )
        {limit_clause};
        """
    )

    con.execute(
        """
        CREATE TEMP VIEW spells2 AS
        SELECT
            s.user_id,
            s.companyname,
            s.soc6,
            date_trunc('month', s.start_date) AS start_m,
            date_trunc('month', s.end_date)   AS end_m,
            COALESCE(m.cbsa, CAST(uc.cbsa AS VARCHAR)) AS cbsa,
            COALESCE(m.lat, uc.lat)   AS lat,
            COALESCE(m.lon, uc.lon)   AS lon,
            ua.gender_category,
            ua.approx_age_2020
        FROM spells AS s
        LEFT JOIN msa_map AS m USING (msa)
        LEFT JOIN user_cbsa AS uc USING (user_id)
        LEFT JOIN user_attr AS ua USING (user_id)
        WHERE (m.cbsa IS NOT NULL OR uc.cbsa IS NOT NULL)
          AND s.companyname IS NOT NULL
          AND s.start_date IS NOT NULL
          AND COALESCE(s.soc6, '') <> '';
        """
    )

    # Month expansion with join/leave flags and age at month
    con.execute(
        """
        CREATE TEMP VIEW month_expanded AS
        SELECT
            user_id,
            companyname,
            soc6,
            cbsa,
            lat,
            lon,
            mon,
            (mon = start_m)::INTEGER AS join_flag,
            (mon = end_m)::INTEGER   AS leave_flag,
            gender_category,
            approx_age_2020,
            (approx_age_2020 - (2020 - EXTRACT(YEAR FROM mon))) AS age_at_mon
        FROM spells2
        JOIN generate_series(start_m, end_m, INTERVAL '1 month') AS gen(mon) ON TRUE;
        """
    )

    # Half-year aggregation with gender counts and age means
    con.execute(
        """
        CREATE TEMP VIEW half_year AS
        SELECT
            companyname,
            ((EXTRACT(YEAR FROM mon)::INT * 2)
             + CASE WHEN EXTRACT(MONTH FROM mon) > 6 THEN 1 ELSE 0 END) AS yh,
            COUNT(DISTINCT user_id) AS headcount,
            COUNT(DISTINCT CASE WHEN gender_category = 'female' THEN user_id END) AS female_headcount,
            COUNT(DISTINCT CASE WHEN join_flag = 1  THEN user_id END) AS joins,
            COUNT(DISTINCT CASE WHEN leave_flag = 1 THEN user_id END) AS leaves,
            COUNT(DISTINCT CASE WHEN join_flag = 1 AND gender_category = 'female' THEN user_id END) AS female_joins,
            COUNT(DISTINCT CASE WHEN leave_flag = 1 AND gender_category = 'female' THEN user_id END) AS female_leaves,
            AVG(DISTINCT CASE WHEN join_flag = 1 THEN age_at_mon END) AS avg_age_hires,
            AVG(DISTINCT age_at_mon) AS avg_age_headcount
        FROM month_expanded
        GROUP BY 1,2;
        """
    )

    # Export
    con.execute(f"COPY half_year TO '{OUT_DEMO_CSV}' (HEADER, DELIMITER ',');")
    con.execute(f"COPY half_year TO '{OUT_DEMO_PARQUET}' (FORMAT 'parquet');")
    print(f"✓ Demography panel written → {OUT_DEMO_CSV.name} & {OUT_DEMO_PARQUET.name}")


def merge_with_firm_panel() -> None:
    # Load demography aggregates (CSV to avoid pyarrow dependency)
    demo = pd.read_csv(OUT_DEMO_CSV)
    demo["yh"] = pd.to_numeric(demo["yh"], errors="coerce").astype("Int64")
    demo["companyname_clean"] = demo["companyname"].str.lower().str.strip()
    demo["yh_index"] = demo["yh"]

    # Lag headcount for rates
    demo.sort_values(["companyname_clean", "yh"], inplace=True)
    demo["headcount_lag"] = demo.groupby("companyname_clean")['headcount'].shift(1)

    # Shares & rates
    demo["female_hires_share"] = demo["female_joins"] / demo["joins"]
    demo.loc[demo["joins"] == 0, "female_hires_share"] = pd.NA

    demo["female_headcount_share"] = demo["female_headcount"] / demo["headcount"]
    demo.loc[demo["headcount"] == 0, "female_headcount_share"] = pd.NA

    demo["female_join_rate"] = demo["female_joins"] / demo["headcount_lag"]
    demo["female_leave_rate"] = demo["female_leaves"] / demo["headcount_lag"]
    for col in ("female_join_rate", "female_leave_rate"):
        demo.loc[demo["headcount_lag"] <= 0, col] = pd.NA

    # Clip implausible ages (same bounds used elsewhere: 18–80)
    for col in ("avg_age_hires", "avg_age_headcount"):
        demo.loc[(demo[col] < 18) | (demo[col] > 80), col] = pd.NA

    # Merge onto existing firm_panel (retain remote/startup vars)
    firm_panel_path = DATA_CLEAN / "firm_panel.dta"
    if not firm_panel_path.exists():
        raise FileNotFoundError(firm_panel_path)

    firm = pd.read_stata(firm_panel_path, convert_categoricals=False)
    # firm_panel yh is a datetime; convert to half-year index = year*2 + (month>6)
    firm["yh_dt"] = pd.to_datetime(firm["yh"], errors="coerce")
    firm["yh_index"] = (firm["yh_dt"].dt.year * 2 + (firm["yh_dt"].dt.month > 6)).astype("Int64")
    firm["companyname_clean"] = firm["companyname"].str.lower().str.strip()

    merged = firm.merge(
        demo,
        on=["companyname_clean", "yh_index"],
        how="left",
        suffixes=("", "_demo"),
    )

    # Drop duplicate companyname column from demo if created
    dup_cols = [c for c in merged.columns if c.endswith("_demo") and c.startswith("companyname")]
    merged = merged.drop(columns=dup_cols)

    # Ensure object columns are string-typed for Stata export
    for col in merged.columns:
        if merged[col].dtype == "object":
            if merged[col].isna().all():
                merged[col] = ""
            else:
                merged[col] = merged[col].astype(str)

    # Persist merged outputs
    merged.to_csv(OUT_MERGED_CSV, index=False)
    merged.to_stata(OUT_MERGED_DTA, write_index=False)
    print(f"✓ firm_panel_demographics written → {OUT_MERGED_CSV.name} & {OUT_MERGED_DTA.name}")


def main() -> None:
    ns = parse_args()
    build_demography(ns)
    merge_with_firm_panel()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"✖ build_firm_demographics_panel failed: {exc}", file=sys.stderr)
        sys.exit(1)
