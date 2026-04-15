#!/usr/bin/env python3
"""
Merge geographic expansion metrics with firm panel for regression analysis.

This script:
1. Loads the firm panel (with remote treatment variables)
2. Loads the geographic expansion metrics  
3. Merges them and exports to Stata format

Output:
-------
data/clean/firm_panel_with_geography.dta
    Ready for regression analysis in Stata
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

# Input files
FIRM_PANEL = PROC / "firm_panel_enriched.csv"
GEO_EXPANSION = PROC / "firm_geographic_expansion.csv"

# Output
OUTPUT_DTA = PROC / "firm_panel_with_geography.dta"
OUTPUT_CSV = PROC / "firm_panel_with_geography.csv"

def main():
    print("\n" + "="*70)
    print("Merging Geographic Expansion Metrics with Firm Panel")
    print("="*70)
    
    # -----------------------------------------------------------------------
    # Load firm panel
    # -----------------------------------------------------------------------
    print("\n1. Loading firm panel...")
    
    # Try CSV first (from Python pipeline)
    if FIRM_PANEL.exists():
        panel = pd.read_csv(FIRM_PANEL)
        print(f"   Loaded from CSV: {len(panel):,} rows, {panel['companyname'].nunique():,} firms")
    else:
        # Fallback to loading from Stata file
        panel_dta = PROC / "firm_panel.dta"
        if panel_dta.exists():
            panel = pd.read_stata(panel_dta)
            print(f"   Loaded from DTA: {len(panel):,} rows, {panel['companyname'].nunique():,} firms")
        else:
            print("ERROR: No firm panel found")
            return False
    
    # Standardize company names
    panel['companyname'] = panel['companyname'].str.lower()
    
    # -----------------------------------------------------------------------
    # Load geographic expansion metrics
    # -----------------------------------------------------------------------
    print("\n2. Loading geographic expansion metrics...")
    geo = pd.read_csv(GEO_EXPANSION)
    print(f"   Loaded: {len(geo):,} rows, {geo['firm'].nunique():,} firms")
    
    # Standardize firm names for merging
    geo['companyname'] = geo['firm'].str.lower()
    
    # Select key variables
    geo_vars = ['companyname', 'yh', 'share_new_geo', 'new_geo_hires', 
                'total_hires', 'n_new_locations', 'n_total_locations']
    geo = geo[geo_vars]
    
    # -----------------------------------------------------------------------
    # Merge datasets
    # -----------------------------------------------------------------------
    print("\n3. Merging datasets...")
    
    # Check overlap
    panel_firms = set(panel['companyname'].unique())
    geo_firms = set(geo['companyname'].unique())
    overlap = panel_firms & geo_firms
    
    print(f"   Firms in panel: {len(panel_firms):,}")
    print(f"   Firms with geo data: {len(geo_firms):,}")
    print(f"   Overlapping firms: {len(overlap):,}")
    
    # Merge
    merged = panel.merge(geo, on=['companyname', 'yh'], how='left', indicator=True)
    
    # Check merge quality
    merge_stats = merged['_merge'].value_counts()
    print("\n   Merge results:")
    print(f"     Both datasets: {merge_stats.get('both', 0):,}")
    print(f"     Panel only: {merge_stats.get('left_only', 0):,}")
    print(f"     Geo only: {merge_stats.get('right_only', 0):,}")
    
    merged.drop('_merge', axis=1, inplace=True)
    
    # -----------------------------------------------------------------------
    # Create additional variables
    # -----------------------------------------------------------------------
    print("\n4. Creating additional variables...")
    
    # Binary indicator for any new geography hiring
    merged['has_new_geo'] = (merged['n_new_locations'] > 0).astype(int)
    
    # Log transformation for count variables
    merged['log_new_locations'] = np.log1p(merged['n_new_locations'])
    
    # Fill missing values for firms with no hiring
    # If no hires, then no new geography expansion
    no_hires = merged['total_hires'].isna() | (merged['total_hires'] == 0)
    merged.loc[no_hires, 'share_new_geo'] = 0
    merged.loc[no_hires, 'n_new_locations'] = 0
    merged.loc[no_hires, 'has_new_geo'] = 0
    
    # Create winsorized versions (1% and 99%)
    for var in ['share_new_geo', 'n_new_locations']:
        if var in merged.columns:
            q01, q99 = merged[var].quantile([0.01, 0.99])
            merged[f'{var}_w'] = merged[var].clip(lower=q01, upper=q99)
    
    # -----------------------------------------------------------------------
    # Summary statistics
    # -----------------------------------------------------------------------
    print("\n5. Summary statistics for key variables:")
    
    # Overall
    print(f"\n   Share in new geography (all periods):")
    print(f"     Mean: {merged['share_new_geo'].mean():.1%}")
    print(f"     Median: {merged['share_new_geo'].median():.1%}")
    print(f"     Std Dev: {merged['share_new_geo'].std():.1%}")
    
    # By COVID period (assuming covid variable exists)
    if 'covid' in merged.columns:
        pre = merged[merged['covid'] == 0]['share_new_geo'].mean()
        post = merged[merged['covid'] == 1]['share_new_geo'].mean()
        print(f"\n   By period:")
        print(f"     Pre-COVID (2019): {pre:.1%}")
        print(f"     Post-COVID (2020+): {post:.1%}")
        print(f"     Difference: {(post - pre):.1%}")
    
    # By remote status (if available)
    if 'remote' in merged.columns:
        print("\n   By remote status (post-COVID):")
        post_data = merged[merged.get('covid', 1) == 1]
        for remote_val in sorted(post_data['remote'].dropna().unique()):
            mean_val = post_data[post_data['remote'] == remote_val]['share_new_geo'].mean()
            print(f"     Remote={remote_val}: {mean_val:.1%}")
    
    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    print("\n6. Exporting merged dataset...")
    
    # Save as CSV
    merged.to_csv(OUTPUT_CSV, index=False)
    print(f"   ✓ Saved to {OUTPUT_CSV}")
    
    # Save as Stata file
    try:
        # Ensure all string columns are properly typed for Stata
        for col in merged.select_dtypes(include=['object']).columns:
            merged[col] = merged[col].astype(str).replace('nan', '')
        
        merged.to_stata(OUTPUT_DTA, write_index=False, version=117)
        print(f"   ✓ Saved to {OUTPUT_DTA}")
    except Exception as e:
        print(f"   ⚠ Could not save Stata file: {e}")
    
    # -----------------------------------------------------------------------
    # Create summary report
    # -----------------------------------------------------------------------
    print("\n7. Key findings for regression:")
    
    # Count firms with geographic expansion data
    has_geo_data = merged['share_new_geo'].notna().sum()
    total_obs = len(merged)
    
    print(f"\n   Coverage:")
    print(f"     Total observations: {total_obs:,}")
    print(f"     With geo expansion data: {has_geo_data:,} ({has_geo_data/total_obs*100:.1f}%)")
    
    # Average effect
    if 'remote' in merged.columns and 'covid' in merged.columns:
        # Simple diff-in-diff
        did_data = merged.dropna(subset=['remote', 'covid', 'share_new_geo'])
        did_table = did_data.pivot_table(
            values='share_new_geo',
            index='remote',
            columns='covid',
            aggfunc='mean'
        )
        
        if 0 in did_table.columns and 1 in did_table.columns:
            print("\n   Simple Diff-in-Diff (share in new geography):")
            print(f"     Non-remote firms:")
            print(f"       Pre:  {did_table.loc[0, 0]:.1%}")
            print(f"       Post: {did_table.loc[0, 1]:.1%}")
            print(f"       Diff: {(did_table.loc[0, 1] - did_table.loc[0, 0]):.1%}")
            
            if 1 in did_table.index:
                print(f"     Remote firms:")
                print(f"       Pre:  {did_table.loc[1, 0]:.1%}")
                print(f"       Post: {did_table.loc[1, 1]:.1%}")
                print(f"       Diff: {(did_table.loc[1, 1] - did_table.loc[1, 0]):.1%}")
                
                did = (did_table.loc[1, 1] - did_table.loc[1, 0]) - \
                      (did_table.loc[0, 1] - did_table.loc[0, 0])
                print(f"\n     DiD estimate: {did:.1%}")
    
    print("\n" + "="*70)
    print("✅ Merge complete! Ready for regression analysis.")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)