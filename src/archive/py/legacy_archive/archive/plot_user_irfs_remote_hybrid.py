#!/usr/bin/env python3
"""Generate IRF plots (remote-first vs hybrid) from rebased Stata outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from writeup.py.plot_style import (
    apply_mpl_defaults,
    apply_standard_figure_layout,
    style_axes,
    errorbar_kwargs,
    FIGSIZE,
    FIG_DPI,
    SERIES_COLOR,
    ERROR_COLOR,
    IRF_YLIMS,
    compute_padded_limits,
    set_integer_xticks,
)
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

apply_mpl_defaults()

RESULTS_DIR = PROJECT_ROOT / "results" / "user_irfs_eng_vs_noneng_remote_hybrid"
# using shared FIGSIZE from plot_style
IRF_LIMITS = {
    ('remote1', 'Engineer'): (-1.5, 5.0),
    ('hybrid', 'Engineer'): (-2.5, 10.0),
}

@dataclass
class PlotSpec:
    group_dir: str
    rhs: str
    outfile: str
    title: str


def load_panel(group: str) -> pd.DataFrame:
    path = RESULTS_DIR / group / "eng_noneng_irf_estimates.dta"
    if not path.exists():
        raise FileNotFoundError(f"Missing results file: {path}")
    df = pd.read_stata(path)
    # Ensure rebased columns exist; fall back to raw coef (should not happen)
    if "coef_rebased" not in df.columns:
        df["coef_rebased"] = df["coef"]
        df["ci_lo_rebased"] = df["ci_lo"]
        df["ci_hi_rebased"] = df["ci_hi"]
    return df




def plot_irf(df: pd.DataFrame, spec: PlotSpec, y_limits: tuple[float, float]) -> None:
    sub = df[df["rhs"] == spec.rhs].copy()
    if sub.empty:
        raise ValueError(f"No rows found for rhs={spec.rhs} in group {spec.group_dir}")

    sub = sub.sort_values("horizon")

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)
    ax.errorbar(
        sub['horizon'],
        sub['coef_rebased'],
        yerr=[sub['coef_rebased'] - sub['ci_lo_rebased'], sub['ci_hi_rebased'] - sub['coef_rebased']],
        fmt='o',
        color=SERIES_COLOR,
        ecolor=ERROR_COLOR,
        elinewidth=1.2,
        capsize=4,
        markersize=5.5,
        markeredgecolor='white',
        markeredgewidth=0.6,
    )
    ax.axhline(0, color='#2f2f2f', linewidth=1.0)
    ax.set_xlabel('Horizon (6-month periods)')
    ax.set_ylabel(r'\Delta Contribution Rank')
    ax.tick_params(axis='both', length=5, width=0.8, colors='#2f2f2f')
    ax.set_title(spec.title)
    set_integer_xticks(ax, sub['horizon'].to_numpy(dtype=float))
    ax.set_ylim(*y_limits)
    apply_standard_figure_layout(fig)

    out_path = RESULTS_DIR / spec.outfile
    fig.savefig(out_path, dpi=FIG_DPI, facecolor='white')
    plt.close(fig)



def main() -> None:
    specs: list[PlotSpec] = [
        PlotSpec("remote1", "Engineer", "irf_remote_eng.png", "Remote-first firms — Engineer growth"),
        PlotSpec("hybrid", "Engineer", "irf_hybrid_eng.png", "Hybrid firms — Engineer growth"),
    ]

    group_frames: dict[str, pd.DataFrame] = {}
    bounds_arrays: list[np.ndarray] = []

    for spec in specs:
        if spec.group_dir not in group_frames:
            try:
                group_frames[spec.group_dir] = load_panel(spec.group_dir)
            except FileNotFoundError:
                continue
        df = group_frames[spec.group_dir]
        sub = df[df["rhs"] == spec.rhs][["ci_lo_rebased", "ci_hi_rebased"]].dropna()
        if not sub.empty:
            bounds_arrays.append(sub.to_numpy(dtype=float))

    if not group_frames:
        return

    if bounds_arrays:
        combined = np.concatenate(bounds_arrays)
        base_limits = compute_padded_limits(combined)
    else:
        base_limits = (-0.2, 0.2)

    for spec in specs:
        df = group_frames.get(spec.group_dir)
        if df is None:
            continue
        limits = base_limits
        preset = IRF_YLIMS.get((spec.group_dir, spec.rhs))
        if preset:
            limits = (max(limits[0], preset[0]), min(limits[1], preset[1]))
            if limits[0] >= limits[1]:
                limits = preset
        plot_irf(df, spec, limits)


if __name__ == "__main__":
    main()
