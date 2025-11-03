#!/usr/bin/env python3
"""Generate Engineer-only IRF plots for Remote-first vs <1 remote share firms.

Reads Stata output under results/user_irfs_engineer_remote/ and rewrites the
per-coefficient PNGs with a shared year-based x-axis and unified styling.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RES_ROOT = os.path.join(BASE, 'results', 'user_irfs_engineer_remote')

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
    'remote1': 'Fully Remote firms',
    'remote_lt1': 'Hybrid/In-Person firms',
}

ROLE_META: Dict[str, Tuple[str, str]] = {
    'Engineer': ('eng', 'Engineer growth'),
}

LEGACY_FILENAME_STEMS: Dict[str, str] = {
    'remote1': 'plot_remote_eng',
    'remote_lt1': 'plot_lt1_eng',
}


def load_group(group: str) -> pd.DataFrame:
    path = os.path.join(RES_ROOT, group, 'engineer_irf_results.csv')
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    needed = {'rhs', 'horizon', 'coef_rebased', 'ci_lo_rebased', 'ci_hi_rebased'}
    if not needed.issubset(df.columns):
        return pd.DataFrame()
    return df.dropna(subset=['rhs', 'horizon', 'coef_rebased'])


def compute_ticks(years: Iterable[float]) -> Tuple[List[float], List[str]]:
    years = [float(y) for y in years if y is not None and math.isfinite(y)]
    if not years:
        return [], []
    min_year = min(years)
    max_year = max(years)
    start = math.floor(min_year)
    end = math.ceil(max_year)
    if end < start:
        start, end = end, start
    ticks = [float(x) for x in range(start, end + 1)]
    if not ticks:
        ticks = [float(round(min_year))]
    labels = [f"{int(t)}" if math.isclose(t, round(t)) else f"{t:g}" for t in ticks]
    return ticks, labels


def save_plot(fig: plt.Figure, outpaths: Sequence[str]) -> None:
    for path in dict.fromkeys(outpaths):  # deduplicate while preserving order
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fig.savefig(path, dpi=FIG_DPI, facecolor='white')


def plot_role(
    df: pd.DataFrame,
    group_label: str,
    role: str,
    ticks: Sequence[float],
    labels: Sequence[str],
    y_limits: Tuple[float, float],
    outpaths: Sequence[str],
) -> None:
    subset = df[df['rhs'] == role].copy()
    if subset.empty:
        return
    subset = subset.sort_values('horizon')
    subset['years'] = subset['horizon'] / 2.0

    color = get_series_color(role)
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)
    ax.axhline(0.0, color=AXIS_COLOR, linewidth=1.0)

    x = subset['years'].to_numpy(dtype=float)
    y = subset['coef_rebased'].to_numpy(dtype=float)
    lower = subset['ci_lo_rebased'].to_numpy(dtype=float)
    upper = subset['ci_hi_rebased'].to_numpy(dtype=float)
    err = [y - lower, upper - y]

    kwargs = errorbar_kwargs(color).copy()
    kwargs['fmt'] = 'o'
    ax.errorbar(x, y, yerr=err, **kwargs)

    ax.set_xlabel('Horizon (years)')
    ax.set_ylabel('Productivity IRF (rebased to year 0)')
    title_suffix = ROLE_META[role][1]
    ax.set_title(f'{group_label} — {title_suffix}')
    if ticks:
        set_integer_xticks(ax, np.asarray(ticks, dtype=float))
        ax.set_xticklabels(labels)
    ax.set_ylim(*y_limits)

    apply_standard_figure_layout(fig)
    save_plot(fig, outpaths)
    plt.close(fig)


def main() -> None:
    os.makedirs(RES_ROOT, exist_ok=True)

    group_frames: Dict[str, pd.DataFrame] = {}
    all_years: List[float] = []
    role_limits: Dict[str, List[float]] = {role: [math.inf, -math.inf] for role in ROLE_META}

    for group in GROUPS:
        df = load_group(group)
        if df.empty:
            continue
        df['horizon'] = pd.to_numeric(df['horizon'], errors='coerce')
        df = df.dropna(subset=['horizon'])
        group_frames[group] = df
        all_years.extend((df['horizon'] / 2.0).tolist())

        for role in ROLE_META:
            role_df = df[df['rhs'] == role]
            if role_df.empty:
                continue
            lo, hi = compute_irf_limits(
                center=role_df['coef_rebased'],
                lower=role_df['ci_lo_rebased'],
                upper=role_df['ci_hi_rebased'],
            )
            cached = role_limits[role]
            cached[0] = min(cached[0], lo)
            cached[1] = max(cached[1], hi)

    ticks, labels = compute_ticks(all_years)

    for role, bounds in role_limits.items():
        lo, hi = bounds
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
            role_limits[role] = [-0.2, 0.2]

    for group, df in group_frames.items():
        group_label = GROUPS.get(group, group)
        suffix = 'remote' if group == 'remote1' else 'lt1'
        role = 'Engineer'
        tag, _ = ROLE_META[role]
        primary = os.path.join(RES_ROOT, f'irf_{suffix}_{tag}.png')
        legacy = os.path.join(RES_ROOT, LEGACY_FILENAME_STEMS[group] + ".png")
        outpaths = [primary, legacy]
        lo, hi = role_limits.get(role, [-0.2, 0.2])
        plot_role(df, group_label, role, ticks, labels, (lo, hi), outpaths)


if __name__ == '__main__':
    main()
