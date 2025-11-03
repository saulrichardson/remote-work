#!/usr/bin/env python3
"""
Find every (user_id, year, month) combination that never appears
between 2016 and 2022 in /Users/saul/Downloads/all_contributions.csv
and save the result to a new CSV in the same folder.
"""

import pandas as pd
from itertools import product
from pathlib import Path

# ----- hard-coded settings ---------------------------------------------------
DATA_PATH   = Path("/Users/saul/Downloads/all_contributions.csv")
START_YEAR  = 2016
END_YEAR    = 2022
OUTPUT_PATH = DATA_PATH.with_name(
    f"missing_user_months_{START_YEAR}_{END_YEAR}.csv"
)
# -----------------------------------------------------------------------------


def main() -> None:
    # Load the data
    df = pd.read_csv(DATA_PATH)
    print(len(df))

    # Ensure correct dtypes
    df["year"]  = df["year"].astype(int)
    df["month"] = df["month"].astype(int)

    # Build the complete user–year–month grid
    users  = df["user_id"].unique()
    years  = range(START_YEAR, END_YEAR + 1)
    months = range(1, 13)

    full_grid = pd.DataFrame(
        product(users, years, months),
        columns=["user_id", "year", "month"]
    )

    # Identify missing combinations
    merged = full_grid.merge(
        df.drop_duplicates(["user_id", "year", "month"]),
        on=["user_id", "year", "month"],
        how="left",
        indicator=True
    )

    missing = (
        merged.loc[merged["_merge"] == "left_only", ["user_id", "year", "month"]]
        .sort_values(["user_id", "year", "month"])
        .reset_index(drop=True)
    )
    print(len(missing))
    # Write result
    missing.to_csv(OUTPUT_PATH, index=False)
    print(f"✅  Missing combinations written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

