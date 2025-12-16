#!/usr/bin/env python3
"""
Plot Engineer vs Non-Engineer IRFs for remote-first vs hybrid firms with
styling aligned to the mini-writeup figures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from project_paths import PY_DIR, RESULTS_CLEANED, ensure_dir  # noqa: E402

if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from plot_style import (  # noqa: E402  pylint: disable=wrong-import-position
    AXIS_COLOR,
    FIGSIZE,
    FIG_DPI,
    apply_mpl_defaults,
    apply_standard_figure_layout,
    compute_irf_limits,
    errorbar_kwargs,
    get_series_color,
    style_axes,
)

apply_mpl_defaults()

GROUPS: Dict[str, str] = {
    "remote1": "Fully Remote",
    "remote_lt1": "Hybrid/In-person",
}

ROLE_META: Dict[str, Tuple[str, str]] = {
    "Engineer": ("remote", "Engineer hiring growth"),
    "NonEngineer": ("hybrid", "Non-Engineer hiring growth"),
}

OUTPUT_STEMS: Dict[str, Dict[str, str]] = {
    "remote1": {
        "Engineer": "panelB_fullremote_engineer.png",
        "NonEngineer": "panelB_fullremote_nonengineer.png",
    },
    "remote_lt1": {
        "Engineer": "panelA_hybrid_engineer.png",
        "NonEngineer": "panelA_hybrid_nonengineer.png",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot remote vs hybrid IRFs")
    parser.add_argument(
        "--results-root",
        type=Path,
        default=RESULTS_CLEANED / "irfs" / "user_irfs_eng_vs_noneng_remote_hybrid",
        help="Directory containing group subfolders with eng_noneng_irf_results.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional override for where PNGs are written (defaults to results-root)",
    )
    return parser.parse_args()


def load_group_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing IRF CSV: {path}")
    df = pd.read_csv(path)
    needed = {"rhs", "horizon", "coef_rebased", "ci_lo_rebased", "ci_hi_rebased"}
    if not needed.issubset(df.columns):
        missing = needed - set(df.columns)
        raise ValueError(f"CSV {path} is missing required columns: {missing}")
    df = df.copy()
    df["horizon"] = pd.to_numeric(df["horizon"], errors="coerce")
    df = df.dropna(subset=["horizon"])
    df["years"] = df["horizon"].astype(float) / 2.0
    return df


def compute_shared_limits(group_frames: Dict[str, pd.DataFrame]) -> Tuple[float, float]:
    centers: List[pd.Series] = []
    lowers: List[pd.Series] = []
    uppers: List[pd.Series] = []
    for df in group_frames.values():
        centers.append(df["coef_rebased"])
        lowers.append(df["ci_lo_rebased"])
        uppers.append(df["ci_hi_rebased"])
    lo, hi = compute_irf_limits(
        center=pd.concat(centers, ignore_index=True),
        lower=pd.concat(lowers, ignore_index=True),
        upper=pd.concat(uppers, ignore_index=True),
        fallback=(-0.5, 0.5),
    )
    return lo, hi


def format_xticks(values: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    ticks = np.unique(np.round(values, 3))
    ticks.sort()
    labels = [f"{tick:g}" for tick in ticks]
    return ticks, labels


def plot_role(
    df: pd.DataFrame,
    group_label: str,
    role: str,
    limits: Tuple[float, float],
    out_path: Path,
) -> None:
    subset = df[df["rhs"] == role].copy()
    if subset.empty:
        return
    subset = subset.sort_values("years")

    color = "#222222"
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)
    ax.axhline(0.0, color=AXIS_COLOR, linewidth=1.0)

    x = subset["horizon"].to_numpy(dtype=float)
    y = subset["coef_rebased"].to_numpy(dtype=float)
    lower = subset["ci_lo_rebased"].to_numpy(dtype=float)
    upper = subset["ci_hi_rebased"].to_numpy(dtype=float)
    err = np.vstack((y - lower, upper - y))
    err = np.nan_to_num(err, nan=0.0)
    err[err < 0.0] = 0.0

    kwargs = errorbar_kwargs(color)
    kwargs["fmt"] = "o"
    ax.errorbar(x, y, yerr=err, **kwargs)

    ticks = np.unique(x)
    labels = [f"H{int(t)}" for t in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Horizon (half-years)")
    ax.set_ylabel("Change in Contribution Rank")
    ax.set_ylim(*limits)

    apply_standard_figure_layout(fig)
    ensure_dir(out_path.parent)
    fig.savefig(out_path, dpi=FIG_DPI, facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    results_root = args.results_root.resolve()
    output_root = args.output_dir.resolve() if args.output_dir else results_root

    group_frames: Dict[str, pd.DataFrame] = {}
    for group in GROUPS:
        csv_path = results_root / group / "eng_noneng_irf_results.csv"
        group_frames[group] = load_group_csv(csv_path)

    global_limits = compute_shared_limits(group_frames)

    for group, df in group_frames.items():
        label = GROUPS[group]
        for role in ROLE_META:
            stem = OUTPUT_STEMS.get(group, {}).get(role)
            if not stem:
                continue
            out_path = output_root / stem
            plot_role(df, label, role, global_limits, out_path)


if __name__ == "__main__":
    main()
