#!/usr/bin/env python3
"""
Plot aggregate firm growth IRFs (growth_rate_we → individual productivity)
for each Remote×Startup group using matplotlib.
Inputs: results/firm_irfs_total_growth/<group>/irf_results.csv
Outputs: clean_firm_irf.png in each group directory.

Groups:
  - remote0_startup0 → "Non-Remote, Non-Startup"
  - remote1_startup0 → "Remote, Non-Startup"
  - remote0_startup1 → "Non-Remote, Startup"
  - remote1_startup1 → "Remote, Startup"
"""

import matplotlib.pyplot as plt
import pandas as pd

from project_paths import RESULTS_DIR

RES_ROOT = RESULTS_DIR / "firm_irfs_total_growth"

GROUPS = {
    'remote0_startup0': 'Non-Remote, Non-Startup',
    'remote1_startup0': 'Remote, Non-Startup',
    'remote0_startup1': 'Non-Remote, Startup',
    'remote1_startup1': 'Remote, Startup',
}

def main():
    any_plotted = False
    for group, label in GROUPS.items():
        gdir = RES_ROOT / group
        csv_path = gdir / "irf_results.csv"
        if not csv_path.exists():
            print(f"[WARN] Missing CSV: {csv_path}")
            continue
        df = pd.read_csv(csv_path)
        needed = {'horizon','coef','ci_lo','ci_hi'}
        if not needed.issubset(df.columns):
            print(f"[WARN] CSV missing columns in {csv_path}")
            continue
        # Ensure numeric
        for c in ['horizon','coef','ci_lo','ci_hi']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        df = df.dropna(subset=['horizon','coef'])
        df = df.sort_values('horizon')

        # Reference line at H0 value if present
        base = None
        d0 = df.loc[df['horizon'] == 0]
        if not d0.empty and pd.notnull(d0['coef'].iloc[0]):
            base = float(d0['coef'].iloc[0])

        fig, ax = plt.subplots(figsize=(9, 6.5))
        ref = 0.0 if base is None else base
        ax.axhline(ref, color='gray', linestyle='--', linewidth=1)

        ax.errorbar(
            df['horizon'], df['coef'],
            yerr=[df['coef'] - df['ci_lo'], df['ci_hi'] - df['coef']],
            fmt='o-', color='navy', ecolor='lightgray', elinewidth=2, capsize=4, markersize=5
        )

        ax.set_xlabel('Horizon (6-month periods)')
        ax.set_ylabel('Effect on Productivity Percentile')
        title = f'Aggregate Firm Growth IRF — {label}'
        if base is not None:
            title += f' (y = H0: {base:.2f})'
        ax.set_title(title)
        ax.set_xticks(sorted(df['horizon'].unique()))
        ax.grid(axis='y', alpha=0.15)
        fig.tight_layout()

        out_png = gdir / "clean_firm_irf.png"
        fig.savefig(out_png, dpi=120)
        plt.close(fig)
        print(f"[OK] {out_png}")
        any_plotted = True

    if not any_plotted:
        print('[INFO] No aggregate plots created. Check inputs.')

if __name__ == '__main__':
    main()
