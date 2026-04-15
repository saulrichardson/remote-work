#!/usr/bin/env python3
"""Build the active non-engineer IRF panel."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.py.project_paths import RESULTS_CLEANED, RESULTS_RAW, ensure_dir
from writeup.py.plot_style import AXIS_COLOR, FIGSIZE, FIG_DPI, apply_mpl_defaults, apply_standard_figure_layout, compute_irf_limits, errorbar_kwargs, style_axes

apply_mpl_defaults()

INPUT = RESULTS_RAW / "17_panelB_fullremote_nonengineer" / "remote1" / "eng_noneng_irf_results.csv"
LIMIT = RESULTS_RAW / "16_panelB_fullremote_engineer" / "remote1" / "eng_noneng_irf_results.csv"
OUTPUT = RESULTS_CLEANED / "irfs" / "user_irfs_eng_vs_noneng_remote_hybrid" / "panelB_fullremote_nonengineer.png"
REQUIRED_COLUMNS = {"rhs", "horizon", "coef_rebased", "ci_lo_rebased", "ci_hi_rebased"}


def load_irf_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing IRF CSV: {path}")
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV {path} is missing required columns: {sorted(missing)}")
    unique_rhs = df["rhs"].dropna().unique().tolist()
    if len(unique_rhs) == 0:
        raise RuntimeError(f"No IRF rows found in {path}")
    if len(unique_rhs) > 1:
        raise RuntimeError(f"CSV {path} contains multiple rhs series {unique_rhs}.")
    df["horizon"] = pd.to_numeric(df["horizon"], errors="coerce")
    for col in ("coef_rebased", "ci_lo_rebased", "ci_hi_rebased"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["horizon"]).sort_values("horizon").reset_index(drop=True)


def main() -> None:
    df = load_irf_csv(INPUT)
    limit_df = load_irf_csv(LIMIT)
    y_limits = compute_irf_limits(
        center=pd.concat([df["coef_rebased"], limit_df["coef_rebased"]], ignore_index=True),
        lower=pd.concat([df["ci_lo_rebased"], limit_df["ci_lo_rebased"]], ignore_index=True),
        upper=pd.concat([df["ci_hi_rebased"], limit_df["ci_hi_rebased"]], ignore_index=True),
        fallback=(-0.5, 0.5),
    )
    x = df["horizon"].to_numpy(dtype=float)
    y = df["coef_rebased"].to_numpy(dtype=float)
    err = np.vstack((y - df["ci_lo_rebased"].to_numpy(dtype=float), df["ci_hi_rebased"].to_numpy(dtype=float) - y))
    err = np.nan_to_num(err, nan=0.0)
    err[err < 0.0] = 0.0
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)
    ax.axhline(0.0, color=AXIS_COLOR, linewidth=1.0)
    kwargs = errorbar_kwargs("#222222")
    kwargs["fmt"] = "o"
    ax.errorbar(x, y, yerr=err, **kwargs)
    ticks = np.unique(x)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"H{int(tick)}" for tick in ticks])
    ax.set_xlabel("Horizon (half-years)")
    ax.set_ylabel("Change in Contribution Rank")
    ax.set_ylim(*y_limits)
    apply_standard_figure_layout(fig)
    ensure_dir(OUTPUT.parent)
    fig.savefig(OUTPUT, dpi=FIG_DPI, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()

