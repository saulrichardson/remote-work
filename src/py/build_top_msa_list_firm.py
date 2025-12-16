#!/usr/bin/env python3
"""Build the employment-ranked MSA list using firm locations."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from project_paths import DATA_PROCESSED


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panel-variant",
        default="precovid",
        help="User panel variant (matches user_panel_<variant>.dta).",
    )
    parser.add_argument(
        "--rank-half",
        default="2019h2",
        help="Half-year label used to rank MSAs by employment.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of MSAs to keep after applying the variation filter.",
    )
    parser.add_argument(
        "--panel-path",
        type=Path,
        help="Optional override for the user panel path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination CSV for the ranked MSAs (defaults to data/clean/top_msas_firm_<variant>.csv).",
    )
    parser.add_argument(
        "--min-nonzero",
        type=int,
        default=5,
        help="Minimum number of non-zero var5 observations required per MSA.",
    )
    return parser.parse_args()


def _first_nonmissing(series: pd.Series) -> str:
    series = series.dropna()
    if series.empty:
        return ""
    return str(series.iloc[0])


def main() -> None:
    args = parse_args()
    panel_path = args.panel_path or (DATA_PROCESSED / f"user_panel_{args.panel_variant}.dta")
    output_path = args.output or (DATA_PROCESSED / f"top_msas_firm_{args.panel_variant}.csv")

    if not panel_path.exists():
        raise FileNotFoundError(f"Panel not found: {panel_path}")

    df = pd.read_stata(panel_path, convert_categoricals=True)
    required_cols = {"company_cbsacode", "msa", "yh", "var5"}
    missing = required_cols - set(df.columns)
    if missing:
        raise KeyError(f"Panel missing required columns: {sorted(missing)}")

    df = df.loc[:, ["company_cbsacode", "msa", "yh", "var5"]].copy()
    df = df.dropna(subset=["company_cbsacode"])
    df["company_cbsacode"] = df["company_cbsacode"].astype(float)

    var5_counts = (
        df.groupby("company_cbsacode")["var5"]
        .apply(lambda s: (s.fillna(0).abs() > 0).sum())
        .astype(int)
    )
    eligible_codes = var5_counts[var5_counts >= args.min_nonzero].index
    df = df[df["company_cbsacode"].isin(eligible_codes)]

    if not pd.api.types.is_datetime64_any_dtype(df["yh"]):
        raise TypeError("Column `yh` must be datetime64 for half-year filtering.")
    month_to_half = {1: "h1", 7: "h2"}
    if not np.isin(df["yh"].dt.month.unique(), list(month_to_half)).all():
        raise ValueError("Unexpected months in `yh`; expected 1 or 7 for half-years.")
    df["yh_label"] = (
        df["yh"].dt.year.astype(int).astype(str) + df["yh"].dt.month.map(month_to_half)
    )
    rank_df = df[df["yh_label"] == args.rank_half]
    if rank_df.empty:
        raise ValueError(f"No observations for {args.rank_half} in the panel.")

    agg = (
        rank_df.groupby("company_cbsacode", as_index=False)
        .agg(
            msa_emp=("var5", "size"),
            msa_name=("msa", _first_nonmissing),
        )
        .sort_values(["msa_emp", "company_cbsacode"], ascending=[False, True])
    )

    lookup_path = DATA_PROCESSED / "cbsa_city_lookup.csv"
    if lookup_path.exists():
        lookup = pd.read_csv(lookup_path)
        lookup = lookup.rename(columns={"CBSA Code": "company_cbsacode", "CBSA Title": "cbsa_title"})
        lookup = lookup.drop_duplicates(subset="company_cbsacode")
        agg = agg.merge(lookup[["company_cbsacode", "cbsa_title"]], how="left", on="company_cbsacode")
        agg["msa_name"] = agg["msa_name"].fillna("").astype(str).str.strip()
        agg["msa_name"] = agg["msa_name"].replace({"empty": "", "Empty": ""})
        agg["msa_name"] = agg["msa_name"].where(agg["msa_name"] != "", agg["cbsa_title"])
        agg = agg.drop(columns=["cbsa_title"])

    if len(agg) < args.top_n:
        raise ValueError(
            f"Only {len(agg)} MSAs meet the variation criteria; requested {args.top_n}."
        )

    top = agg.head(args.top_n).copy()
    top["msa_rank"] = range(1, len(top) + 1)
    top = top[["company_cbsacode", "msa_name", "msa_rank", "msa_emp"]]
    top.to_csv(output_path, index=False)
    print(f"Saved ranked MSAs → {output_path}")


if __name__ == "__main__":
    main()
