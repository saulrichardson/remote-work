#!/usr/bin/env python3
"""Prepare an event-study panel for remote hires (precovid sample only).

Outputs a slim .dta with event_time around the *remote hire* date, carrying
the destination firm type (startup vs large) onto all pre/post observations.
This keeps pre-hire rows (even if remote==0) so we can estimate pre-trends.
Regression will be run in Stata.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))  # ensure project_paths import
from project_paths import DATA_CLEAN, DATA_SAMPLES, ensure_dir  # type: ignore

INPUT_PANEL = DATA_CLEAN / "user_panel_precovid.dta"
OUTPUT_DTA = DATA_CLEAN / "user_hire_event_panel_precovid.dta"
OUTPUT_CSV = DATA_SAMPLES / "user_hire_event_panel_precovid.csv"

# Half-year window
LEAD_LAG = 4


def parse_start_date(df: pd.DataFrame) -> pd.Series:
    """Return a pandas datetime for the hire date.

    Tries columns in order: start_date (ISO), start (Stata date string),
    start_mon (YYYYmM). Falls back to NaT when parsing fails.
    """

    date = pd.NaT
    if "start_date" in df.columns:
        date = pd.to_datetime(df["start_date"], errors="coerce")
    if date.isna().all() and "start" in df.columns:
        date = pd.to_datetime(df["start"], errors="coerce")
    if date.isna().all() and "start_mon" in df.columns:
        # start_mon like 2017m6; replace 'm' with '-' and parse first of month
        date = pd.to_datetime(df["start_mon"].astype(str).str.replace("m", "-", regex=False) + "-01", errors="coerce")
    return date


def compute_half_index(year: pd.Series, half: pd.Series) -> pd.Series:
    """Convert year + half (1/2) to a sequential half-year index."""
    return year.astype(int) * 2 + (half.astype(int) - 1)


def main() -> None:
    df = pd.read_stata(INPUT_PANEL, convert_categoricals=False)

    if "y" not in df.columns or "half" not in df.columns:
        raise RuntimeError("Expected columns 'y' and 'half' in user panel")

    # Identify first remote hire per user
    remote_rows = df[df["remote"] == 1].copy()
    if remote_rows.empty:
        raise RuntimeError("No remote hires found in panel")

    hire_dt = parse_start_date(remote_rows)
    remote_rows["hire_idx"] = hire_dt.dt.year * 2 + ((hire_dt.dt.month - 1) // 6)
    remote_rows = remote_rows.dropna(subset=["hire_idx", "user_id"])

    # Earliest remote hire per user (destination firm type comes from that row)
    hire_info = (
        remote_rows.sort_values(["user_id", "hire_idx"])
        .groupby("user_id")
        .first()[["hire_idx", "startup"]]
        .rename(columns={"startup": "dest_startup"})
    )
    hire_info["dest_startup"] = hire_info["dest_startup"].fillna(0).astype("int8")
    hire_info["dest_large"] = (1 - hire_info["dest_startup"]).astype("int8")

    # Attach hire info to full panel; keep only users with a remote hire
    df = df.merge(hire_info, left_on="user_id", right_index=True, how="inner")

    # Panel half-year index from existing y/half columns
    df["panel_idx"] = compute_half_index(df["y"], df["half"])

    # Event time relative to remote hire
    df["event_time"] = df["panel_idx"] - df["hire_idx"]

    # Keep window
    df = df[df["event_time"].between(-LEAD_LAG, LEAD_LAG)]

    # Keep necessary columns for Stata regression
    keep_cols = [
        "user_id",
        "firm_id",
        "yh",
        "event_time",
        "dest_startup",
        "dest_large",
        "remote",
        "startup",
        "company_teleworkable",
        "total_contributions_q100",
        "total_contributions",
        "total_contributions_we",
    ]
    missing = [c for c in keep_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing expected columns in panel: {missing}")

    out = df[keep_cols].copy()

    # Cast to compact types
    for col in ["user_id", "firm_id"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["event_time"] = out["event_time"].astype("int8")
    out["dest_startup"] = out["dest_startup"].astype("int8")
    out["dest_large"] = out["dest_large"].astype("int8")

    # Drop rows with missing outcomes
    out = out[out["total_contributions_q100"].notna()]

    ensure_dir(OUTPUT_DTA.parent)
    out.to_stata(OUTPUT_DTA, write_index=False, version=118)
    ensure_dir(OUTPUT_CSV.parent)
    out.head(5000).to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {OUTPUT_DTA} (n={len(out):,})")
    print(f"Sample CSV: {OUTPUT_CSV} (first 5k rows)")


if __name__ == "__main__":
    main()
