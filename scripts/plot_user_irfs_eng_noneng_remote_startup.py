#!/usr/bin/env python3
"""
LEGACY WORKFLOW – maintained for reference only.

Plots engineer vs non-engineer IRFs (two RHS) split by Remote×Startup using
archived CSV outputs in `results/user_irfs_eng_vs_noneng_by_remote_startup/`.

This code predates the current remote-vs-hybrid pipeline. Do not run new Stata
jobs expecting to feed it; instead see `plot_user_irfs_eng_noneng_remote.py` for
the active workflow and `results/user_irfs_eng_vs_noneng_remote_hybrid/` for
fresh outputs.
"""

import math
import os

import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RES_ROOT = os.path.join(BASE, 'results', 'user_irfs_eng_vs_noneng_by_remote_startup')

GROUPS = {
    'remote0_startup0': 'Non-Remote, Non-Startup',
    'remote1_startup0': 'Remote, Non-Startup',
    'remote0_startup1': 'Non-Remote, Startup',
    'remote1_startup1': 'Remote, Startup',
}


def load_group_csv(group):
    path = os.path.join(RES_ROOT, group, 'eng_noneng_irf_results.csv')
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    for col in ['horizon', 'coef', 'ci_lo', 'ci_hi']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['horizon', 'coef'])
    return df


def _format_tick_labels(ticks):
    labels = []
    for val in ticks:
        as_float = float(val)
        if math.isclose(as_float, round(as_float)):
            labels.append(str(int(round(as_float))))
        else:
            labels.append(f"{as_float:g}")
    return labels


def plot_group(df, label, out_png_abs, out_png_rb, y_limits_abs=None, y_limits_rb=None,
               x_ticks=None, tick_labels=None):
    piv = df.pivot(index='horizon', columns='rhs', values=['coef', 'ci_lo', 'ci_hi']).sort_index()
    h_years = piv.index.values / 2.0
    if x_ticks is None:
        ticks = sorted(set(h_years))
        labels = _format_tick_labels(ticks)
    else:
        ticks = list(x_ticks)
        labels = tick_labels if tick_labels is not None else _format_tick_labels(ticks)

    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
    for rhs, color in [('Engineer', 'navy'), ('NonEngineer', 'darkorange')]:
        if ('coef', rhs) not in piv.columns:
            continue
        horizons = h_years
        coef = piv[('coef', rhs)].values
        lo = piv[('ci_lo', rhs)].values
        hi = piv[('ci_hi', rhs)].values
        yerr = [coef - lo, hi - coef]
        ax.errorbar(horizons, coef, yerr=yerr, fmt='o-', color=color, ecolor='lightgray',
                    elinewidth=2, capsize=4, markersize=5, label=rhs)
    ax.set_xlabel('Horizon (years)')
    ax.set_ylabel('Effect on Productivity Percentile')
    ax.set_title(f'Eng vs Non-Eng IRF — {label} (absolute)')
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    if y_limits_abs is not None:
        ax.set_ylim(*y_limits_abs)
    ax.grid(axis='y', alpha=0.15)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png_abs, dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 6.5))
    ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
    for rhs, color in [('Engineer', 'navy'), ('NonEngineer', 'darkorange')]:
        if ('coef', rhs) not in piv.columns:
            continue
        horizons = h_years
        coef = piv[('coef', rhs)].values
        lo = piv[('ci_lo', rhs)].values
        hi = piv[('ci_hi', rhs)].values
        base_series = piv[('coef', rhs)]
        base = base_series.loc[0] if 0 in base_series.index else base_series.iloc[0]
        coef_rb = coef - base
        lo_rb = lo - base
        hi_rb = hi - base
        yerr_rb = [coef_rb - lo_rb, hi_rb - coef_rb]
        ax.errorbar(horizons, coef_rb, yerr=yerr_rb, fmt='o-', color=color, ecolor='lightgray',
                    elinewidth=2, capsize=4, markersize=5, label=rhs)
    ax.set_xlabel('Horizon (years)')
    ax.set_ylabel('Effect on Productivity Percentile (rebased)')
    ax.set_title(f'Eng vs Non-Eng IRF — {label} (rebased)')
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    if y_limits_rb is not None:
        ax.set_ylim(*y_limits_rb)
    ax.grid(axis='y', alpha=0.15)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png_rb, dpi=120)
    plt.close(fig)


def main():
    os.makedirs(RES_ROOT, exist_ok=True)

    group_data = {}
    ymin_abs = ymax_abs = None
    ymin_rb = ymax_rb = None
    all_horizons = set()

    for group, label in GROUPS.items():
        df = load_group_csv(group)
        if df is None or df.empty:
            print(f"[WARN] Missing or empty CSV for {group}")
            continue
        piv = df.pivot(index='horizon', columns='rhs', values=['coef', 'ci_lo', 'ci_hi']).sort_index()
        piv_rb = piv.copy()
        rhs_values = piv.columns.get_level_values(1).unique()
        for rhs in rhs_values:
            if ('coef', rhs) not in piv.columns:
                continue
            base_series = piv[('coef', rhs)]
            base = base_series.loc[0] if 0 in base_series.index else base_series.iloc[0]
            for metric in ['coef', 'ci_lo', 'ci_hi']:
                if (metric, rhs) in piv_rb.columns:
                    piv_rb[(metric, rhs)] = piv_rb[(metric, rhs)] - base
        lo_abs = piv['ci_lo'].min().min()
        hi_abs = piv['ci_hi'].max().max()
        if pd.notna(lo_abs):
            ymin_abs = lo_abs if ymin_abs is None else min(ymin_abs, lo_abs)
        if pd.notna(hi_abs):
            ymax_abs = hi_abs if ymax_abs is None else max(ymax_abs, hi_abs)
        lo_rb = piv_rb['ci_lo'].min().min()
        hi_rb = piv_rb['ci_hi'].max().max()
        if pd.notna(lo_rb):
            ymin_rb = lo_rb if ymin_rb is None else min(ymin_rb, lo_rb)
        if pd.notna(hi_rb):
            ymax_rb = hi_rb if ymax_rb is None else max(ymax_rb, hi_rb)
        all_horizons.update(piv.index.tolist())
        group_data[group] = {
            'label': label,
            'df': df,
            'piv': piv,
            'piv_rb': piv_rb,
        }

    if not group_data:
        return

    horizon_years = [h / 2.0 for h in sorted(all_horizons)]
    if horizon_years:
        min_year = min(horizon_years)
        max_year = max(horizon_years)
        start_tick = math.floor(min_year)
        end_tick = math.ceil(max_year)
        x_ticks = [float(i) for i in range(start_tick, end_tick + 1)]
    else:
        x_ticks = []
    tick_labels = _format_tick_labels(x_ticks)
    y_limits_abs = (ymin_abs, ymax_abs) if ymin_abs is not None and ymax_abs is not None else None
    y_limits_rb = (ymin_rb, ymax_rb) if ymin_rb is not None and ymax_rb is not None else None

    for group, info in group_data.items():
        gdir = os.path.join(RES_ROOT, group)
        os.makedirs(gdir, exist_ok=True)
        out_abs = os.path.join(gdir, 'irf_plot_absolute.png')
        out_rb = os.path.join(gdir, 'irf_plot_rebased.png')
        plot_group(info['df'], info['label'], out_abs, out_rb,
                   y_limits_abs=y_limits_abs, y_limits_rb=y_limits_rb,
                   x_ticks=x_ticks, tick_labels=tick_labels)

    order = ['remote0_startup0', 'remote1_startup0', 'remote0_startup1', 'remote1_startup1']
    if y_limits_abs is not None:
        fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)
        axes = axes.flatten()
        for ax, key in zip(axes, order):
            if key not in group_data:
                ax.axis('off')
                continue
            info = group_data[key]
            piv = info['piv']
            ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
            for rhs, color in [('Engineer', 'navy'), ('NonEngineer', 'darkorange')]:
                if ('coef', rhs) not in piv.columns:
                    continue
                horizons = piv.index.values / 2.0
                coef = piv[('coef', rhs)].values
                lo = piv[('ci_lo', rhs)].values
                hi = piv[('ci_hi', rhs)].values
                yerr = [coef - lo, hi - coef]
                ax.errorbar(horizons, coef, yerr=yerr, fmt='o-', color=color, ecolor='lightgray',
                            elinewidth=2, capsize=4, markersize=5, label=rhs)
            ax.set_title(f"{info['label']} (absolute)")
            ax.set_ylim(*y_limits_abs)
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(tick_labels)
            ax.grid(axis='y', alpha=0.15)
        for idx, ax in enumerate(axes):
            ax.set_xlabel('Horizon (years)')
            if idx in (0, 2):
                ax.set_ylabel('Effect on Productivity')
        fig.suptitle('Eng vs Non-Eng IRFs (Absolute, Shared Y)')
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        out_comb_abs = os.path.join(RES_ROOT, 'combined_irf_absolute.png')
        fig.savefig(out_comb_abs, dpi=120)
        plt.close(fig)
        print(f"[OK] {out_comb_abs}")

    if y_limits_rb is not None:
        fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)
        axes = axes.flatten()
        for ax, key in zip(axes, order):
            if key not in group_data:
                ax.axis('off')
                continue
            info = group_data[key]
            piv_rb = info['piv_rb']
            ax.axhline(0.0, color='gray', linestyle='--', linewidth=1)
            for rhs, color in [('Engineer', 'navy'), ('NonEngineer', 'darkorange')]:
                if ('coef', rhs) not in piv_rb.columns:
                    continue
                horizons = piv_rb.index.values / 2.0
                coef_rb = piv_rb[('coef', rhs)].values
                lo_rb = piv_rb[('ci_lo', rhs)].values
                hi_rb = piv_rb[('ci_hi', rhs)].values
                yerr_rb = [coef_rb - lo_rb, hi_rb - coef_rb]
                ax.errorbar(horizons, coef_rb, yerr=yerr_rb, fmt='o-', color=color, ecolor='lightgray',
                            elinewidth=2, capsize=4, markersize=5, label=rhs)
            ax.set_title(f"{info['label']} (rebased)")
            ax.set_ylim(*y_limits_rb)
            ax.set_xticks(x_ticks)
            ax.set_xticklabels(tick_labels)
            ax.grid(axis='y', alpha=0.15)
        for idx, ax in enumerate(axes):
            ax.set_xlabel('Horizon (years)')
            if idx in (0, 2):
                ax.set_ylabel('Effect on Productivity (rebased)')
        fig.suptitle('Eng vs Non-Eng IRFs (Rebased, Shared Y)')
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        out_comb_rb = os.path.join(RES_ROOT, 'combined_irf_rebased.png')
        fig.savefig(out_comb_rb, dpi=120)
        plt.close(fig)
        print(f"[OK] {out_comb_rb}")


if __name__ == '__main__':
    main()
