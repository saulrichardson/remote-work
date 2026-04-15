#!/usr/bin/env python3
"""
Build composition changes with correct yh values from the data
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

# Create directory
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("Building composition changes...")
    
    # Based on data exploration:
    # 2019 H2 = yh 4039
    # 2020 H2 = yh 4041
    # 2021 H1 = yh 4042
    
    pre_covid_yh = 4039
    post_covid_yhs = [4041, 4042]
    
    # Read firm-SOC panel (in chunks for memory efficiency)
    print("Processing SOC composition changes...")
    
    chunks = []
    for chunk in pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv", 
                            usecols=['companyname', 'soc4', 'yh', 'headcount'],
                            chunksize=500000):
        # Filter to relevant periods
        relevant = chunk[chunk['yh'].isin([pre_covid_yh] + post_covid_yhs)]
        if len(relevant) > 0:
            chunks.append(relevant)
    
    df = pd.concat(chunks, ignore_index=True)
    print(f"Loaded {len(df)} rows for relevant periods")
    
    # Pre-COVID
    pre_df = df[df['yh'] == pre_covid_yh].groupby(['companyname', 'soc4'])['headcount'].sum()
    print(f"Pre-COVID: {len(pre_df)} firm-SOC combinations")
    
    # Post-COVID average
    post_df = df[df['yh'].isin(post_covid_yhs)].groupby(['companyname', 'soc4', 'yh'])['headcount'].sum()
    post_df = post_df.groupby(['companyname', 'soc4']).mean()
    print(f"Post-COVID: {len(post_df)} firm-SOC combinations")
    
    # Calculate changes
    merged = pd.DataFrame({
        'pre': pre_df,
        'post': post_df
    }).fillna(0)
    
    # Calculate % change
    merged['pct_change'] = np.where(
        merged['pre'] > 0,
        100 * (merged['post'] - merged['pre']) / merged['pre'],
        np.where(merged['post'] > 0, 100, 0)
    )
    
    # Get top 15 SOCs
    soc_totals = merged.groupby(level='soc4')['pre'].sum().sort_values(ascending=False)
    top_socs = soc_totals.head(15).index.tolist()
    
    print(f"\nTop 15 SOCs: {top_socs}")
    
    # Create wide format
    wide_df = merged['pct_change'].unstack(level='soc4')[top_socs].fillna(0)
    wide_df.columns = [f'pct_chg_soc{col}' for col in wide_df.columns]
    wide_df = wide_df.reset_index()
    
    # Save
    wide_df.to_csv(RESULTS_DIR / "firm_soc_composition.csv", index=False)
    print(f"\nSaved SOC composition for {len(wide_df)} firms")
    
    # Also save to Stata format
    wide_df.to_stata(RESULTS_DIR / "firm_soc_composition.dta", write_index=False)
    
    # Summary statistics
    print("\nSummary of composition changes:")
    for col in [c for c in wide_df.columns if 'pct_chg' in c]:
        soc = col.replace('pct_chg_soc', '')
        mean_chg = wide_df[col].mean()
        print(f"SOC {soc}: avg change = {mean_chg:.1f}%")
    
    # Test on a few firms
    print("\nExample firms:")
    print(wide_df.head())
    
    return wide_df

if __name__ == "__main__":
    composition_df = main()
    print("\nDone! Next steps:")
    print("1. Run 'stata -b do spec/composition_tests_prep.do' to merge with panels")
    print("2. Run scaling and productivity regressions")