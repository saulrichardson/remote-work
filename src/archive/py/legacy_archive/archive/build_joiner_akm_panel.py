#!/usr/bin/env python3
"""Build joiner-level panel with AKM FEs and firm treatments from user panel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb  # type: ignore
import numpy as np
import pandas as pd


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construct joiner-level dataset with AKM and firm treatments"
    )
    parser.add_argument(
        "--spells",
        required=True,
        help="Path to data/raw/Scoop_workers_positions.csv",
    )
    parser.add_argument(
        "--user-panel",
        default="data/clean/user_panel_precovid_akm.dta",
        help="Path to user_panel_precovid_akm.dta",
    )
    parser.add_argument(
        "--akm-dir",
        default="../New/Data/AKM",
        help="Directory containing AKM_Estimate_PFE_*.csv",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Destination .dta file",
    )
    parser.add_argument(
        "--parquet",
        help="Optional Parquet output",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=500_000,
        help="Row chunk size when streaming spells",
    )
    return parser.parse_args()


def _clean_company(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.lower()
        .str.strip()
        .str.replace(r",+$", "", regex=True)
    )


def _extract_joiners(spells_path: Path, chunksize: int) -> pd.DataFrame:
    con = duckdb.connect()
    con.execute("PRAGMA threads=4;")
    query = f"""
        WITH spells AS (
            SELECT
                TRY_CAST(user_id AS BIGINT) AS user_id,
                companyname AS companyname_raw,
                LOWER(TRIM(REGEXP_REPLACE(companyname, ',+$', ''))) AS company_clean,
                TRY_CAST(start_date AS DATE) AS start_date
            FROM read_csv_auto(
                '{spells_path}',
                header=true,
                strict_mode=false,
                all_varchar=true,
                ignore_errors=true,
                null_padding=true
            )
            WHERE user_id IS NOT NULL
              AND companyname IS NOT NULL
              AND start_date IS NOT NULL
        )
        SELECT
            user_id,
            companyname_raw,
            company_clean,
            start_date,
            DATE_TRUNC('month', start_date) AS start_month,
            EXTRACT(year FROM start_date)::INTEGER AS year,
            CASE WHEN EXTRACT(month FROM start_date) <= 6 THEN 1 ELSE 2 END AS half,
            CASE
                WHEN EXTRACT(month FROM start_date) <= 6
                    THEN MAKE_DATE(EXTRACT(year FROM start_date)::INTEGER, 1, 1)
                ELSE MAKE_DATE(EXTRACT(year FROM start_date)::INTEGER, 7, 1)
            END AS yh_date,
            ROW_NUMBER() OVER (
                PARTITION BY user_id, company_clean
                ORDER BY start_date
            ) AS rn
        FROM spells
    """
    joiners = con.execute(query).fetch_df()
    con.close()

    joiners = joiners[joiners["rn"] == 1].drop(columns=["rn"] )
    joiners = joiners.rename(columns={"companyname_raw": "companyname"})
    joiners["yh_date"] = pd.to_datetime(joiners["yh_date"])
    joiners["start_month"] = pd.to_datetime(joiners["start_month"])
    joiners["start_date"] = pd.to_datetime(joiners["start_date"])
    joiners["user_id"] = joiners["user_id"].astype("Int64")
    joiners["yh"] = joiners["year"] * 2 + (joiners["half"] == 2).astype(int)
    return joiners


def _load_user_panel(path: Path) -> pd.DataFrame:
    cols = [
        "user_id",
        "firm_id",
        "yh",
        "companyname",
        "remote",
        "covid",
        "startup",
        "company_teleworkable",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
    ]
    panel = pd.read_stata(path, columns=cols)
    panel["company_clean"] = _clean_company(panel["companyname"])
    panel["yh_date"] = pd.to_datetime(panel["yh"])
    panel["firm_id"] = panel["firm_id"].astype(str)
    return panel


def _load_panel_map(panel: pd.DataFrame) -> pd.DataFrame:
    keep_cols = [
        "company_clean",
        "yh_date",
        "firm_id",
        "remote",
        "covid",
        "startup",
        "company_teleworkable",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
    ]
    map_df = panel[keep_cols].sort_values(["company_clean", "yh_date", "firm_id"])
    map_df = map_df.drop_duplicates(subset=["company_clean", "yh_date"])
    return map_df


def _load_person_akm(akm_dir: Path) -> pd.DataFrame:
    akm_dir = akm_dir.expanduser()
    files = {
        "akm_pfe_norm_2013to19": "AKM_Estimate_PFE_2013to19.csv",
        "akm_pfe_norm_2016to19": "AKM_Estimate_PFE_2016to19.csv",
    }
    frames: list[pd.DataFrame] = []
    for colname, filename in files.items():
        csv_path = akm_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"AKM file not found: {csv_path}")
        df = pd.read_csv(csv_path, usecols=["user_id", "normalizedPFE_pct"])
        df["user_id"] = df["user_id"].round().astype("Int64")
        df = df.rename(columns={"normalizedPFE_pct": colname})
        frames.append(df)
    akm = frames[0]
    for frame in frames[1:]:
        akm = akm.merge(frame, on="user_id", how="outer")
    return akm


def _write_outputs(df: pd.DataFrame, output_path: Path, parquet_path: Path | None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_stata(str(output_path), version=118, write_index=False)
    if parquet_path is not None:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)


def main() -> None:
    args = _parse_args()
    spells_path = Path(args.spells).expanduser()
    user_panel_path = Path(args.user_panel).expanduser()
    akm_dir = Path(args.akm_dir).expanduser()
    output_path = Path(args.output).expanduser()
    parquet_path = Path(args.parquet).expanduser() if args.parquet else None

    for path in (spells_path, user_panel_path, akm_dir):
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    if output_path.suffix.lower() != ".dta":
        raise ValueError("--output must end with .dta")

    print("Extracting first-entry joiners…", flush=True)
    joiners = _extract_joiners(spells_path, args.chunksize)
    print(f"Joiner rows: {len(joiners):,}", flush=True)

    print("Loading user panel…", flush=True)
    panel = _load_user_panel(user_panel_path)
    panel_map = _load_panel_map(panel)

    print("Merging joiners with firm treatments…", flush=True)
    merged = joiners.merge(
        panel_map,
        left_on=["company_clean", "yh_date"],
        right_on=["company_clean", "yh_date"],
        how="left",
        suffixes=("", "_panel"),
    )

    missing_firm = merged["firm_id"].isna().sum()
    if missing_firm:
        print(f"Dropping {missing_firm:,} joiners without firm coverage", flush=True)
        merged = merged.dropna(subset=["firm_id"])

    merged["firm_id"] = merged["firm_id"].astype(str)

    print("Merging person AKM estimates…", flush=True)
    person_akm = _load_person_akm(akm_dir)
    merged = merged.merge(person_akm, on="user_id", how="left")

    merged = merged[
        [
            "user_id",
            "companyname",
            "company_clean",
            "firm_id",
            "start_date",
            "start_month",
            "year",
            "half",
            "yh_date",
            "yh",
            "remote",
            "covid",
            "startup",
            "company_teleworkable",
            "var3",
            "var4",
            "var5",
            "var6",
            "var7",
            "akm_pfe_norm_2013to19",
            "akm_pfe_norm_2016to19",
        ]
    ]

    merged = merged.sort_values(["user_id", "start_date"]).reset_index(drop=True)

    print(f"Rows retained: {len(merged):,}", flush=True)
    print(f"Rows with AKM: {merged['akm_pfe_norm_2013to19'].notna().sum():,}", flush=True)

    print(f"Writing output to {output_path}…", flush=True)
    _write_outputs(merged, output_path=output_path, parquet_path=parquet_path)
    print("Done.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # pragma: no cover
        print(f"ERROR: {err}", file=sys.stderr)
        raise
