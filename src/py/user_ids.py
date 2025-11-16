#!/usr/bin/env python3
"""Find (user, year, month) combinations missing from an activity CSV."""

from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

import pandas as pd

from project_paths import DATA_RAW


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Identify user-year-month combinations absent from a contributions "
            "CSV and export them as a companion file."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DATA_RAW / "all_contributions.csv",
        help="Path to the contributions CSV (default: data/raw/all_contributions.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the output CSV (defaults to alongside --input)",
    )
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2022)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = args.input.expanduser().resolve()
    if args.output:
        output_path = args.output.expanduser().resolve()
    else:
        output_path = data_path.with_name(
            f"missing_user_months_{args.start_year}_{args.end_year}.csv"
        )

    if not data_path.exists():
        raise FileNotFoundError(
            f"Contributions file not found: {data_path}. Place it under data/raw or use --input."
        )

    df = pd.read_csv(data_path)
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)

    users = df["user_id"].unique()
    years = range(args.start_year, args.end_year + 1)
    months = range(1, 13)

    full_grid = pd.DataFrame(
        product(users, years, months),
        columns=["user_id", "year", "month"],
    )

    merged = full_grid.merge(
        df.drop_duplicates(["user_id", "year", "month"]),
        on=["user_id", "year", "month"],
        how="left",
        indicator=True,
    )

    missing = (
        merged.loc[merged["_merge"] == "left_only", ["user_id", "year", "month"]]
        .sort_values(["user_id", "year", "month"])
        .reset_index(drop=True)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    missing.to_csv(output_path, index=False)
    print(f"✅  Missing combinations written to {output_path}")


if __name__ == "__main__":
    main()
