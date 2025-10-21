#!/usr/bin/env python3
"""
Plot per-role IRFs for each Remote×Startup group using Matplotlib with shared styling.

Inputs: results/composition_irfs_all7_by_remote_startup/<group>/all7_irf_results.csv
Outputs: clean_irf_<Role>.png in each group directory.

Groups:
  - remote0_startup0 → "Non-Remote, Non-Startup"
  - remote1_startup0 → "Remote, Non-Startup"
  - remote0_startup1 → "Non-Remote, Startup"
  - remote1_startup1 → "Remote, Startup"
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, Iterable, List, Sequence

import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RES_ROOT = os.path.join(BASE, 'results', 'composition_irfs_all7_by_remote_startup')

PY_DIR = os.path.join(BASE, 'py')
if PY_DIR not in sys.path:
    sys.path.insert(0, PY_DIR)

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
    set_integer_xticks,
)

apply_mpl_defaults()

GROUPS: Dict[str, str] = {
    'remote0_startup0': 'Non-Remote, Non-Startup',
    'remote1_startup0': 'Remote, Non-Startup',
    'remote0_startup1': 'Non-Remote, Startup',
    'remote1_startup1': 'Remote, Startup',
}

ROLES: List[str] = [
    'Admin', 'Engineer', 'Finance', 'Marketing', 'Operations', 'Sales', 'Scientist',
]


def save_plot(fig: plt.Figure, outpath: str) -> None:
    directory = os.path.dirname(outpath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fig.savefig(outpath, dpi=FIG_DPI, facecolor='white')


def plot_role(
    df: pd.DataFrame,
    role: str,
    color_index: int,
    outpath: str,
    title_suffix: str,
    y_limits: tuple[float, float],
    *,
    rebase: bool = False,
    baseline_at_h0: bool = True,
) -> bool:
    subset = df[df['role'] == role].copy()
    if subset.empty:
        return False
    subset = subset.sort_values('horizon')

    base = None
    if 0 in subset['horizon'].to_numpy(dtype=float):
        base_row = subset.loc[subset['horizon'] == 0]
        if not base_row.empty and pd.notnull(base_row['coef'].iloc[0]):
            base = float(base_row['coef'].iloc[0])

    if rebase and base is not None:
        subset['coef'] = subset['coef'] - base
        if {'ci_lo', 'ci_hi'}.issubset(subset.columns):
            subset['ci_lo'] = subset['ci_lo'] - base
            subset['ci_hi'] = subset['ci_hi'] - base

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)
    ref = 0.0 if rebase or not baseline_at_h0 or base is None else base
    ax.axhline(ref, color=AXIS_COLOR, linewidth=1.0)

    color = get_series_color(role, index=color_index)
    kwargs = errorbar_kwargs(color).copy()
    kwargs['fmt'] = 'o'
    x = subset['horizon'].to_numpy(dtype=float)
    y = subset['coef'].to_numpy(dtype=float)
    lower = subset['ci_lo'].to_numpy(dtype=float)
    upper = subset['ci_hi'].to_numpy(dtype=float)
    ax.errorbar(x, y, yerr=[y - lower, upper - y], **kwargs)

    ax.set_xlabel('Horizon (6-month periods)')
    ax.set_ylabel('Effect on Productivity Percentile')
    subtitle = 'rebased to H0' if rebase else (f'y = H0 ({base:.2f})' if base is not None and baseline_at_h0 else None)
    title = f'IRF: {role} — {title_suffix}'
    if subtitle:
        title = f'{title} ({subtitle})'
    ax.set_title(title)
    horizons = subset['horizon'].to_numpy(dtype=float)
    set_integer_xticks(ax, horizons)
    ax.set_ylim(*y_limits)

    apply_standard_figure_layout(fig)
    save_plot(fig, outpath)
    plt.close(fig)
    return True


def compute_role_limits(group_frames: Dict[str, pd.DataFrame]) -> Dict[str, tuple[float, float]]:
    limits: Dict[str, List[float]] = {role: [math.inf, -math.inf] for role in ROLES}
    for df in group_frames.values():
        for role in ROLES:
            role_df = df[df['role'] == role]
            if role_df.empty:
                continue
            lo, hi = compute_irf_limits(
                center=role_df['coef'],
                lower=role_df.get('ci_lo'),
                upper=role_df.get('ci_hi'),
            )
            cached = limits[role]
            cached[0] = min(cached[0], lo)
            cached[1] = max(cached[1], hi)
    final: Dict[str, tuple[float, float]] = {}
    for role, (lo, hi) in limits.items():
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
            final[role] = (-0.2, 0.2)
        else:
            final[role] = (lo, hi)
    return final


def main() -> int:
    group_frames: Dict[str, pd.DataFrame] = {}
    for group in GROUPS:
        gdir = os.path.join(RES_ROOT, group)
        csv_path = os.path.join(gdir, 'all7_irf_results.csv')
        if not os.path.exists(csv_path):
            print(f"[WARN] Missing CSV: {csv_path}")
            continue
        df = pd.read_csv(csv_path)
        needed = {'role', 'horizon', 'coef', 'ci_lo', 'ci_hi'}
        if not needed.issubset(df.columns):
            print(f"[WARN] CSV missing columns in {csv_path}")
            continue
        for col in needed - {'role'}:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        group_frames[group] = df.dropna(subset=['horizon', 'coef'])

    if not group_frames:
        print("[INFO] No plots created. Check inputs.")
        return 0

    role_limits = compute_role_limits(group_frames)
    any_plotted = False

    for group, df in group_frames.items():
        label = GROUPS[group]
        gdir = os.path.join(RES_ROOT, group)
        for idx, role in enumerate(ROLES):
            out_png = os.path.join(gdir, f'clean_irf_{role}.png')
            ok = plot_role(
                df,
                role,
                idx,
                out_png,
                label,
                role_limits.get(role, (-0.2, 0.2)),
            )
            if ok:
                any_plotted = True
                print(f"[OK] {out_png}")
            else:
                print(f"[SKIP] No data for role {role} in {group}")

    if not any_plotted:
        print("[INFO] No plots created. Check inputs.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
