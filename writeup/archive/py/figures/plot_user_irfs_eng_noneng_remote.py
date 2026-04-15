#!/usr/bin/env python3
"""Plot a single engineer/non-engineer IRF panel from an asset-owned CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
WRITEUP_PY = PROJECT_ROOT / "writeup" / "py"
SRC_PY = PROJECT_ROOT / "src" / "py"
if str(WRITEUP_PY) not in sys.path:
    sys.path.insert(0, str(WRITEUP_PY))
if str(SRC_PY) not in sys.path:
    sys.path.insert(0, str(SRC_PY))

from project_paths import RESULTS_CLEANED, RESULTS_RAW, ensure_dir  # noqa: E402
from plot_style import (  # noqa: E402  pylint: disable=wrong-import-position
    AXIS_COLOR,
    FIGSIZE,
    FIG_DPI,
    apply_mpl_defaults,
    apply_standard_figure_layout,
    compute_irf_limits,
    errorbar_kwargs,
    style_axes,
)

apply_mpl_defaults()

REQUIRED_COLUMNS = {"rhs", "horizon", "coef_rebased", "ci_lo_rebased", "ci_hi_rebased"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot an asset-owned IRF CSV")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=RESULTS_RAW / "16_panelB_fullremote_engineer" / "remote1" / "eng_noneng_irf_results.csv",
        help="Input CSV produced by the numbered Stata asset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED / "irfs" / "user_irfs_eng_vs_noneng_remote_hybrid" / "panelB_fullremote_engineer.png",
        help="Output PNG path",
    )
    parser.add_argument(
        "--limit-csv",
        action="append",
        type=Path,
        default=None,
        help="Additional IRF CSVs to include when computing shared y-axis limits",
    )
    parser.add_argument(
        "--rhs",
        help="Optional rhs filter when the CSV contains more than one series",
    )
    return parser.parse_args()


def load_irf_csv(path: Path, rhs: str | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing IRF CSV: {path}")

    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV {path} is missing required columns: {sorted(missing)}")

    df = df.copy()
    if rhs:
        df = df[df["rhs"] == rhs].copy()

    unique_rhs = df["rhs"].dropna().unique().tolist()
    if len(unique_rhs) == 0:
        raise RuntimeError(f"No IRF rows found in {path}")
    if len(unique_rhs) > 1:
        raise RuntimeError(
            f"CSV {path} contains multiple rhs series {unique_rhs}. "
            "Pass --rhs to select one."
        )

    df["horizon"] = pd.to_numeric(df["horizon"], errors="coerce")
    for col in ("coef_rebased", "ci_lo_rebased", "ci_hi_rebased"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["horizon"]).sort_values("horizon").reset_index(drop=True)
    return df


def compute_limits(main_df: pd.DataFrame, extra_frames: List[pd.DataFrame]) -> tuple[float, float]:
    centers = [main_df["coef_rebased"]]
    lowers = [main_df["ci_lo_rebased"]]
    uppers = [main_df["ci_hi_rebased"]]

    for frame in extra_frames:
        centers.append(frame["coef_rebased"])
        lowers.append(frame["ci_lo_rebased"])
        uppers.append(frame["ci_hi_rebased"])

    return compute_irf_limits(
        center=pd.concat(centers, ignore_index=True),
        lower=pd.concat(lowers, ignore_index=True),
        upper=pd.concat(uppers, ignore_index=True),
        fallback=(-0.5, 0.5),
    )


def main() -> None:
    args = parse_args()

    df = load_irf_csv(args.input_csv.resolve(), rhs=args.rhs)
    extra_frames: List[pd.DataFrame] = []
    for extra in args.limit_csv or []:
        extra_frames.append(load_irf_csv(extra.resolve(), rhs=args.rhs))

    y_limits = compute_limits(df, extra_frames)

    x = df["horizon"].to_numpy(dtype=float)
    y = df["coef_rebased"].to_numpy(dtype=float)
    lower = df["ci_lo_rebased"].to_numpy(dtype=float)
    upper = df["ci_hi_rebased"].to_numpy(dtype=float)
    err = np.vstack((y - lower, upper - y))
    err = np.nan_to_num(err, nan=0.0)
    err[err < 0.0] = 0.0

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)
    ax.axhline(0.0, color=AXIS_COLOR, linewidth=1.0)

    kwargs = errorbar_kwargs("#222222")
    kwargs["fmt"] = "o"
    ax.errorbar(x, y, yerr=err, **kwargs)

    ticks = np.unique(x)
    labels = [f"H{int(tick)}" for tick in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Horizon (half-years)")
    ax.set_ylabel("Change in Contribution Rank")
    ax.set_ylim(*y_limits)

    apply_standard_figure_layout(fig)
    ensure_dir(args.output.parent)
    fig.savefig(args.output, dpi=FIG_DPI, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
