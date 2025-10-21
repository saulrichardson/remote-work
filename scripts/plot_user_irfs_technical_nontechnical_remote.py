#!/usr/bin/env python3
"""Generate IRF plots (Technical vs Non-Technical growth) for remote splits.

Reads Stata output under results/user_irfs_technical_vs_nontechnical_remote/
and rewrites the per-coefficient PNGs with a shared year-based x-axis.
"""

import math
import os
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RES_ROOT = os.path.join(BASE, 'results', 'user_irfs_technical_vs_nontechnical_remote')

GROUPS: Dict[str, str] = {
    'remote1': 'Remote-first firms',
    'remote_lt1': 'Remote share < 1',
}

ROLE_META: Dict[str, Tuple[str, str, str]] = {
    'Technical': ('technical', 'Technical growth (Eng+Scientist)', 'midnightblue'),
    'NonTechnical': ('nontechnical', 'Non-Technical growth', 'firebrick'),
}


def load_group(group: str) -> pd.DataFrame:
    path = os.path.join(RES_ROOT, group, 'technical_irf_results.csv')
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    needed = {'rhs', 'horizon', 'coef_rebased', 'ci_lo_rebased', 'ci_hi_rebased'}
    if not needed.issubset(df.columns):
        return pd.DataFrame()
    df = df.dropna(subset=['rhs', 'horizon', 'coef_rebased'])
    return df


def compute_ticks(years: List[float]) -> Tuple[List[float], List[str]]:
    if not years:
        return [], []
    min_year = min(years)
    max_year = max(years)
    if math.isnan(min_year) or math.isnan(max_year):
        return [], []
    start = math.floor(min_year)
    end = math.ceil(max_year)
    if end < start:
        start, end = end, start
    ticks = [float(x) for x in range(start, end + 1)]
    if not ticks:
        ticks = [float(round(min_year))]
    labels = []
    for val in ticks:
        if math.isclose(val, round(val)):
            labels.append(str(int(round(val))))
        else:
            labels.append(f"{val:g}")
    return ticks, labels


def axis_limits(series: pd.Series) -> Tuple[float, float]:
    series = series.dropna()
    if series.empty:
        return (-0.2, 0.2)
    lo = float(series.min())
    hi = float(series.max())
    if math.isnan(lo) or math.isnan(hi):
        return (-0.2, 0.2)
    span = hi - lo
    if span <= 0:
        span = 0.1
    pad = span * 0.1
    ymin = lo - pad
    ymax = hi + pad
    if math.isclose(ymax, ymin):
        ymin -= 0.1
        ymax += 0.1
    return ymin, ymax


def plot_role(df: pd.DataFrame, group_label: str, role: str,
              ticks: List[float], labels: List[str],
              y_limits: Tuple[float, float], outfile: str, color: str) -> None:
    subset = df[df['rhs'] == role].copy()
    if subset.empty:
        return
    subset['years'] = subset['horizon'] / 2.0
    subset = subset.sort_values('years')

    fig, ax = plt.subplots(figsize=(8, 5.4))
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
    x = subset['years'].to_numpy()
    y = subset['coef_rebased'].to_numpy()
    yerr = [y - subset['ci_lo_rebased'].to_numpy(),
            subset['ci_hi_rebased'].to_numpy() - y]
    ax.errorbar(x, y, yerr=yerr, fmt='o-', color=color, ecolor='lightgray',
                elinewidth=2, capsize=4, markersize=5)

    ax.set_xlabel('Horizon (years)')
    ax.set_ylabel('Productivity IRF (rebased to year 0)')
    ax.set_title(f'{group_label} — {ROLE_META[role][1]}')
    if ticks:
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels)
    ax.set_ylim(*y_limits)
    ax.grid(axis='y', alpha=0.15)

    fig.tight_layout()
    fig.savefig(outfile, dpi=120)
    plt.close(fig)


def main() -> None:
    os.makedirs(RES_ROOT, exist_ok=True)

    group_frames: Dict[str, pd.DataFrame] = {}
    all_years: List[float] = []
    role_limits: Dict[str, Tuple[float, float]] = {}

    for role in ROLE_META:
        role_limits[role] = (-0.2, 0.2)

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
            lo_hi = axis_limits(pd.concat([
                role_df['ci_lo_rebased'],
                role_df['ci_hi_rebased']
            ]))
            current_lo, current_hi = role_limits.get(role, (-0.2, 0.2))
            role_limits[role] = (
                min(current_lo, lo_hi[0]),
                max(current_hi, lo_hi[1])
            )

    ticks, labels = compute_ticks(all_years)

    for group, df in group_frames.items():
        group_label = GROUPS.get(group, group)
        for role, (tag, _, color) in ROLE_META.items():
            suffix = 'remote' if group == 'remote1' else 'lt1'
            outfile = os.path.join(RES_ROOT, f'irf_{suffix}_{tag}.png')
            y_limits = role_limits.get(role, (-0.2, 0.2))
            plot_role(df, group_label, role, ticks, labels, y_limits, outfile, color)


if __name__ == '__main__':
    main()
