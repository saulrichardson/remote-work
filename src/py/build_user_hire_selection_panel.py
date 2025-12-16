#!/usr/bin/env python3
"""Construct hire-level panel to test selection on productivity.

For each user job switch (change in firm_id), create one observation with:
  - hire_yh: half-year of the new job's first observed period
  - old_prod: mean total_contributions_q100 over the TWO half-years BEFORE hire
    at the previous firm (yh ∈ [hire_yh-2, hire_yh-1])
  - new_prod: mean total_contributions_q100 over the TWO half-years AFTER hire
    at the new firm (yh ∈ [hire_yh, hire_yh+1])
  - delta_prod: new_prod - old_prod
We enforce a *strict* window: hires are kept only if both pre and post windows
have two observed halves (old_nobs==2 & new_nobs==2). Covariates are taken at
the hire half-year for the *new* firm.

Outputs are written to data/clean and a sample CSV to data/samples.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

from project_paths import DATA_CLEAN, DATA_SAMPLES, ensure_dir

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class HireWindowMeans:
    mean: float | np.floating | None
    nobs: int

    @property
    def is_valid(self) -> bool:
        return self.mean is not None and not pd.isna(self.mean) and self.nobs > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_window_mean(
    df: pd.DataFrame, firm_id: float, idx_start: int, idx_end: int
) -> HireWindowMeans:
    """Return mean total_contributions_q100 and count for firm_id within half-index window."""
    mask = (
        (df["firm_id"] == firm_id)
        & (df["half_index"] >= idx_start)
        & (df["half_index"] <= idx_end)
        & df["total_contributions_q100"].notna()
    )
    window = df.loc[mask, "total_contributions_q100"]
    if window.empty:
        return HireWindowMeans(mean=None, nobs=0)
    return HireWindowMeans(mean=float(window.mean()), nobs=int(window.shape[0]))


def detect_hires(panel: pd.DataFrame) -> pd.DataFrame:
    """Identify job changes per user.

    A hire event is the first observation where firm_id != previous firm_id.
    Returns a DataFrame subset with one row per hire event, carrying prev_firm_id.
    """

    panel = panel.sort_values(["user_id", "half_index"]).copy()
    panel["prev_firm_id"] = panel.groupby("user_id")["firm_id"].shift(1)
    hire_flag = (
        panel["firm_id"].notna()
        & panel["prev_firm_id"].notna()
        & (panel["firm_id"] != panel["prev_firm_id"])
    )
    hires = panel.loc[hire_flag].copy()
    return hires


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_panel(input_path: Path, output_base: Path) -> Tuple[int, int]:
    df = pd.read_stata(input_path, convert_categoricals=False)

    required_cols = [
        "user_id",
        "firm_id",
        "yh",
        "total_contributions_q100",
        "remote",
        "startup",
        "covid",
        "var3",
        "var4",
        "var5",
        "company_teleworkable",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing expected columns in input panel: {missing}")

    # Keep only the columns we need to stay lightweight
    df = df[required_cols].copy()
    df["yh"] = pd.to_datetime(df["yh"])
    # half_index: integer counting half-years, Jan/Jul coded as 0/1 within year
    df["half_index"] = df["yh"].dt.year.astype(int) * 2 + (df["yh"].dt.month > 6).astype(int)

    hires = detect_hires(df)
    if hires.empty:
        raise RuntimeError("No hire events detected in panel")

    records = []

    grouped = df.groupby("user_id")
    for _, row in hires.iterrows():
        user_id = row["user_id"]
        new_firm = row["firm_id"]
        prev_firm = row["prev_firm_id"]
        hire_idx = int(row["half_index"])
        hire_yh = row["yh"]

        user_panel = grouped.get_group(user_id)

        old_window = compute_window_mean(user_panel, prev_firm, hire_idx - 2, hire_idx - 1)
        new_window = compute_window_mean(user_panel, new_firm, hire_idx, hire_idx + 1)

        # Strict requirement: need exactly two observed halves on each side
        if not (old_window.is_valid and new_window.is_valid):
            continue
        if not (old_window.nobs == 2 and new_window.nobs == 2):
            continue

        old_prod = old_window.mean
        new_prod = new_window.mean
        delta_prod = new_prod - old_prod if (old_prod is not None and new_prod is not None) else None

        records.append(
            {
                "user_id": user_id,
                "firm_id": new_firm,
                "prev_firm_id": prev_firm,
                "hire_yh": hire_yh,
                "hire_half_index": hire_idx,
                "old_prod": old_prod,
                "new_prod": new_prod,
                "delta_prod": delta_prod,
                "old_nobs": old_window.nobs,
                "new_nobs": new_window.nobs,
                "remote": row["remote"],
                "startup": row["startup"],
                "covid": row["covid"],
                "var3": row["var3"],
                "var4": row["var4"],
                "var5": row["var5"],
                "company_teleworkable": row["company_teleworkable"],
            }
        )

    if not records:
        raise RuntimeError("All hire events dropped due to missing window data")

    out_df = pd.DataFrame.from_records(records)

    # Cast to compact types
    for col in ["user_id", "firm_id", "prev_firm_id", "old_nobs", "new_nobs"]:
        out_df[col] = pd.to_numeric(out_df[col], errors="coerce")
    out_df["hire_half_index"] = pd.to_numeric(out_df["hire_half_index"], errors="coerce").astype("Int64")

    # Write outputs
    ensure_dir(output_base.parent)
    out_df.to_stata(output_base.with_suffix(".dta"), write_index=False, version=118)

    ensure_dir(DATA_SAMPLES)
    sample_path = DATA_SAMPLES / (output_base.name + ".csv")
    out_df.head(5000).to_csv(sample_path, index=False)

    return out_df.shape[0], out_df["user_id"].nunique()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hire selection panel (old vs new productivity).")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="User panel variant to load (default: %(default)s)",
    )
    args = parser.parse_args()

    input_path = DATA_CLEAN / f"user_panel_{args.variant}.dta"
    output_base = DATA_CLEAN / f"user_hire_selection_panel_{args.variant}"

    n_rows, n_users = build_panel(input_path, output_base)
    print(f"Wrote {output_base}.dta (n={n_rows:,} hires; {n_users:,} users)")
    print(f"Sample CSV: {DATA_SAMPLES / (output_base.name + '.csv')}")


if __name__ == "__main__":
    main()
