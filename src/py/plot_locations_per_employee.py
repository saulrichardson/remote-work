#!/usr/bin/env python3
"""
Plot the ratio of locations to employees across user, firm, and LinkedIn panels.

The script summarises three tiers of data:
1. User panel (`data/cleaned/user_panel_<variant>.dta`)
2. Firm panel (`data/cleaned/firm_panel.dta` + `firm_headcount_breadth.csv`)
3. LinkedIn firm×MSA panel (e.g. `data/cleaned/linkedin_panel_with_remote.parquet`)

For each half-year it computes:
    ratio = (# distinct firm-location pairs with headcount > 0) / (total employees)

Usage (default paths assume the standard repo layout):
    python src/py/plot_locations_per_employee.py \
        --user-panel data/cleaned/user_panel_precovid.dta \
        --firm-panel data/cleaned/firm_panel.dta \
        --firm-breadth data/cleaned/firm_headcount_breadth.csv \
        --linkedin-panel data/cleaned/linkedin_panel_with_remote.parquet \
        --output results/cleaned/figures/locations_per_employee.png \
        --export-data results/raw/locations_per_employee.csv
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import duckdb
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from project_paths import RESULTS_CLEANED_FIGURES

TIER_LABELS = {
    "user_panel": "User panel",
    "firm_panel": "Firm panel",
    "linkedin_panel": "LinkedIn (firm×MSA)",
}

GROUP_LABELS = {
    "all": "All firms",
    "startup": "Startups",
    "nonstartup": "Non-startups",
}


def _coerce_halfyear_int(value) -> int | float:
    """
    Convert various half-year representations to the integer code y*2 + (h-1).
    Supports Stata yh ints/floats, pandas Timestamps, and strings like '2017h2'.
    """
    if value is None:
        return np.nan
    if isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
        ts = value if isinstance(value, pd.Timestamp) else value.to_pydatetime()
        year = ts.year
        half = 1 if ts.month <= 6 else 2
        return year * 2 + (half - 1)
    if isinstance(value, (np.datetime64,)):
        ts = pd.Timestamp(value)
        year = ts.year
        half = 1 if ts.month <= 6 else 2
        return year * 2 + (half - 1)
    if isinstance(value, str):
        text = value.strip().lower()
        match = re.match(r"^(\d{4})\s*h?\s*([12])$", text)
        if match:
            year = int(match.group(1))
            half = int(match.group(2))
            return year * 2 + (half - 1)
        if text.isdigit():
            return int(text)
        return np.nan
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return np.nan if math.isnan(value) else int(value)
    if hasattr(value, "year") and hasattr(value, "month"):
        year = int(value.year)
        half = 1 if int(value.month) <= 6 else 2
        return year * 2 + (half - 1)
    return np.nan


def _halfyear_to_timestamp(yh_int: int) -> pd.Timestamp:
    """Map y*2+(h-1) code to a Timestamp pointing at the first day of the half-year."""
    if pd.isna(yh_int):
        return pd.NaT
    yh_int = int(yh_int)
    year = yh_int // 2
    half = 1 if yh_int % 2 == 0 else 2
    month = 1 if half == 1 else 7
    return pd.Timestamp(year=year, month=month, day=1)


def _finalise_frame(df: pd.DataFrame, tier: str, group: str) -> pd.DataFrame:
    df = df.copy()
    df = df[(df["n_emp"] > 0) & (df["n_locations"] > 0)]
    df["ratio"] = df["n_locations"] / df["n_emp"]
    df["tier"] = tier
    df["group"] = group
    group_label = GROUP_LABELS.get(group, group.title())
    if group == "all":
        df["series"] = TIER_LABELS.get(tier, tier)
    else:
        df["series"] = f"{TIER_LABELS.get(tier, tier)} ({group_label})"
    df["period"] = df["yh_int"].apply(_halfyear_to_timestamp)
    df = df.dropna(subset=["period", "ratio"])
    return df.sort_values("period")


def aggregate_user_panel(path: Path) -> pd.DataFrame:
    cols = ["user_id", "yh", "companyname", "company_cbsacode", "startup"]
    df = pd.read_stata(path.as_posix(), columns=cols, convert_categoricals=False)
    df = df.dropna(subset=["user_id", "yh", "companyname", "company_cbsacode"])
    df["companyname_lower"] = df["companyname"].str.strip().str.lower()
    df["company_cbsa"] = (
        df["companyname_lower"].astype(str) + "::" + df["company_cbsacode"].astype(str)
    )
    df["yh_int"] = df["yh"].apply(_coerce_halfyear_int).astype("Int64")
    df["startup_flag"] = df["startup"].fillna(0).astype(int)

    frames: list[pd.DataFrame] = []
    group_defs = {
        "all": df,
        "startup": df[df["startup_flag"] == 1],
        "nonstartup": df[df["startup_flag"] == 0],
    }
    for group, subset in group_defs.items():
        if subset.empty:
            continue
        grouped = (
            subset.groupby("yh_int")
            .agg(
                n_locations=("company_cbsa", pd.Series.nunique),
                n_emp=("user_id", pd.Series.nunique),
            )
            .reset_index()
        )
        frames.append(_finalise_frame(grouped, "user_panel", group))
    return pd.concat(frames, ignore_index=True)


def load_firm_panel(path: Path) -> pd.DataFrame:
    cols = ["companyname", "yh", "total_employees", "startup"]
    df = pd.read_stata(path.as_posix(), columns=cols, convert_categoricals=False)
    df = df.dropna(subset=["companyname", "yh"])
    df["companyname_lower"] = df["companyname"].str.strip().str.lower()
    df["yh_int"] = (
        df["yh"].dt.year * 2 + (df["yh"].dt.month.gt(6)).astype(int)
    ).astype("Int64")
    df["startup_flag"] = df["startup"].fillna(0).astype(int)
    df["total_employees"] = df["total_employees"].fillna(0)
    return df


def aggregate_firm_panel(firm: pd.DataFrame, breadth_path: Path) -> pd.DataFrame:
    firm = firm.copy()
    firm = firm.dropna(subset=["total_employees"])
    firm = firm[firm["total_employees"] > 0]

    breadth = pd.read_csv(breadth_path)
    breadth["companyname_lower"] = breadth["companyname_lower"].str.strip().str.lower()
    breadth = breadth.rename(columns={"yh": "yh_int"})

    merged = pd.merge(
        firm,
        breadth,
        on=["companyname_lower", "yh_int"],
        how="inner",
        validate="m:1",
    )
    merged = merged.dropna(subset=["n_cbsa_headcount"])
    merged = merged[merged["n_cbsa_headcount"] > 0]

    frames: list[pd.DataFrame] = []
    group_defs = {
        "all": merged,
        "startup": merged[merged["startup_flag"] == 1],
        "nonstartup": merged[merged["startup_flag"] == 0],
    }
    for group, subset in group_defs.items():
        if subset.empty:
            continue
        grouped = (
            subset.groupby("yh_int")
            .agg(
                n_locations=("n_cbsa_headcount", "sum"),
                n_emp=("total_employees", "sum"),
            )
            .reset_index()
        )
        frames.append(_finalise_frame(grouped, "firm_panel", group))
    return pd.concat(frames, ignore_index=True)


def aggregate_linkedin_panel(path: Path, firm_flags: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect()
    table = (
        f"read_parquet('{path.as_posix()}')"
        if path.suffix.lower() in {'.parquet', '.pq'}
        else f"read_csv_auto('{path.as_posix()}', header=True)"
    )
    con.execute(
        f"""
        CREATE TEMP VIEW base AS
        SELECT
            lower(companyname) AS companyname_lower,
            cbsa,
            CAST(yh AS BIGINT) AS yh_int,
            SUM(headcount) AS headcount
        FROM {table}
        WHERE headcount IS NOT NULL
          AND headcount > 0
          AND cbsa IS NOT NULL
        GROUP BY 1, 2, 3;
        """
    )

    all_df = con.execute(
        "SELECT yh_int, COUNT(*) AS n_locations, SUM(headcount) AS n_emp FROM base GROUP BY 1 ORDER BY 1"
    ).fetchdf()

    flags = (
        firm_flags[["companyname_lower", "yh_int", "startup_flag"]]
        .dropna(subset=["companyname_lower", "yh_int"])
        .drop_duplicates(subset=["companyname_lower", "yh_int"])
    )
    con.register("firm_startup_flags", flags)
    matched_df = con.execute(
        """
        SELECT
            b.yh_int,
            f.startup_flag,
            COUNT(*) AS n_locations,
            SUM(b.headcount) AS n_emp
        FROM base b
        JOIN firm_startup_flags f
          ON b.companyname_lower = f.companyname_lower
         AND b.yh_int = f.yh_int
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    ).fetchdf()
    con.close()

    frames: list[pd.DataFrame] = []
    frames.append(_finalise_frame(all_df, "linkedin_panel", "all"))

    for flag, group in [(1, "startup"), (0, "nonstartup")]:
        subset = matched_df[matched_df["startup_flag"] == flag].drop(columns="startup_flag")
        if subset.empty:
            continue
        frames.append(_finalise_frame(subset, "linkedin_panel", group))

    return pd.concat(frames, ignore_index=True)


def plot_ratios(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 5))
    for label, section in df.groupby("series"):
        ax.plot(
            section["period"],
            section["ratio"],
            marker="o",
            linewidth=2,
            label=label,
        )
    ax.set_xlabel("Half-year")
    ax.set_ylabel("Locations per employee")
    ax.xaxis.set_major_locator(mdates.YearLocator(base=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y %b"))
    ax.legend()
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-panel",
        type=Path,
        default=Path("data/cleaned/user_panel_precovid.dta"),
        help="Path to the user panel .dta file.",
    )
    parser.add_argument(
        "--firm-panel",
        type=Path,
        default=Path("data/cleaned/firm_panel.dta"),
        help="Path to the firm panel .dta file.",
    )
    parser.add_argument(
        "--firm-breadth",
        type=Path,
        default=Path("data/cleaned/firm_headcount_breadth.csv"),
        help="CSV with per-firm counts of CBSAs with headcount.",
    )
    parser.add_argument(
        "--linkedin-panel",
        type=Path,
        default=Path("data/cleaned/linkedin_panel_with_remote.parquet"),
        help="LinkedIn firm×MSA panel (parquet or CSV).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED_FIGURES / "locations_per_employee.png",
        help="Destination PNG path for the plot.",
    )
    parser.add_argument(
        "--export-data",
        type=Path,
        help="Optional CSV to write the aggregated ratios.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    firm_panel = load_firm_panel(args.firm_panel)
    frames = [
        aggregate_user_panel(args.user_panel),
        aggregate_firm_panel(firm_panel, args.firm_breadth),
        aggregate_linkedin_panel(args.linkedin_panel, firm_panel),
    ]
    combined = pd.concat(frames, ignore_index=True)

    tier_bounds = combined.groupby("tier")["period"].agg(["min", "max"]).dropna()
    common_start = tier_bounds["min"].max()
    common_end = tier_bounds["max"].min()
    if pd.isna(common_start) or pd.isna(common_end) or common_start >= common_end:
        filtered = combined
    else:
        mask = (combined["period"] >= common_start) & (combined["period"] <= common_end)
        filtered = combined[mask]

    plot_ratios(filtered, args.output)
    if args.export_data:
        args.export_data.parent.mkdir(parents=True, exist_ok=True)
        filtered.to_csv(
            args.export_data,
            index=False,
            date_format="%Y-%m-%d",
        )
    print(f"Saved plot to {args.output}")
    if args.export_data:
        print(f"Saved aggregated series to {args.export_data}")


if __name__ == "__main__":
    main()
