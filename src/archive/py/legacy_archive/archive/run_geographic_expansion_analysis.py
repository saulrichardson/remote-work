#!/usr/bin/env python3
"""
Run geographic expansion analysis with proper treatment variables.
Merges firm panel with geographic expansion metrics and performs analysis.
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

def main():
    print("="*70)
    print("Geographic Expansion Analysis")
    print("="*70)
    
    # Load firm panel with treatment variables
    print("\n1. Loading firm panel...")
    panel = pd.read_stata(PROC / "firm_panel.dta")
    print(f"   Loaded: {len(panel):,} observations, {panel['companyname'].nunique():,} firms")
    
    # Check treatment variables
    print("\n2. Treatment variables in panel:")
    for var in ['var3', 'var5', 'var4', 'var6', 'var7', 'remote', 'teleworkable', 'covid']:
        if var in panel.columns:
            non_missing = panel[var].notna().sum()
            print(f"   {var:15s}: {non_missing:,} non-missing, mean={panel[var].mean():.3f}")
    
    # Load geographic expansion data
    print("\n3. Loading geographic expansion data...")
    geo = pd.read_csv(PROC / "firm_geographic_expansion.csv")
    geo['companyname'] = geo['firm'].str.lower()
    panel['companyname'] = panel['companyname'].str.lower()
    
    # Fix yh type mismatch - convert datetime to integer half-year format
    if str(panel['yh'].dtype).startswith('datetime'):
        # Convert datetime to half-year integer
        # January = H1, July = H2
        panel['year'] = panel['yh'].dt.year
        panel['half'] = panel['yh'].apply(lambda x: 2 if x.month == 7 else 1)
        panel['yh_int'] = panel['year'] * 2 + panel['half'] - 1
    else:
        panel['yh_int'] = panel['yh'].astype(int)
    
    geo['yh_int'] = geo['yh'].astype(int)
    
    print(f"   Loaded: {len(geo):,} firm-periods with expansion data")
    print(f"   YH range in panel: {panel['yh_int'].min()} to {panel['yh_int'].max()}")
    print(f"   YH range in geo: {geo['yh'].min()} to {geo['yh'].max()}")
    
    # Merge datasets
    print("\n4. Merging datasets...")
    
    # Prepare geo data for merge
    geo_merge = geo[['companyname', 'yh_int', 'share_new_geo', 'new_geo_hires', 
                     'total_hires', 'n_new_locations']].copy()
    geo_merge.columns = ['companyname', 'yh_int', 'share_new_geo', 'new_geo_hires',
                          'total_hires', 'n_new_locations']
    
    merged = panel.merge(
        geo_merge,
        on=['companyname', 'yh_int'],
        how='left',
        indicator=True
    )
    
    merge_counts = merged['_merge'].value_counts()
    print(f"   Both datasets: {merge_counts.get('both', 0):,}")
    print(f"   Panel only: {merge_counts.get('left_only', 0):,}")
    
    # Focus on observations with geographic data
    analysis_df = merged[merged['_merge'] == 'both'].copy()
    print(f"\n5. Analysis sample: {len(analysis_df):,} observations")
    
    # Summary statistics
    print("\n6. Summary Statistics for share_new_geo:")
    print(f"   Mean: {analysis_df['share_new_geo'].mean():.3f}")
    print(f"   Std Dev: {analysis_df['share_new_geo'].std():.3f}")
    print(f"   Median: {analysis_df['share_new_geo'].median():.3f}")
    
    # By COVID period
    pre_covid = analysis_df[analysis_df['covid'] == 0]['share_new_geo'].mean()
    post_covid = analysis_df[analysis_df['covid'] == 1]['share_new_geo'].mean()
    print(f"\n   Pre-COVID (should be ~0): {pre_covid:.3f}")
    print(f"   Post-COVID: {post_covid:.3f}")
    
    # Simple difference by treatment
    print("\n7. Simple Analysis (Post-COVID only):")
    post_df = analysis_df[analysis_df['covid'] == 1].copy()
    
    if 'remote' in post_df.columns:
        by_remote = post_df.groupby('remote')['share_new_geo'].agg(['mean', 'std', 'count'])
        print("\n   Share new geography by remote status:")
        print(by_remote)
        
        if 1 in by_remote.index and 0 in by_remote.index:
            diff = by_remote.loc[1, 'mean'] - by_remote.loc[0, 'mean']
            print(f"\n   Simple difference: {diff:.3f} ({diff*100:.1f} percentage points)")
    
    # Check var3 (remote × covid interaction)
    print("\n8. Treatment Effect Analysis:")
    
    # Focus on observations with complete treatment variables
    complete_df = analysis_df.dropna(subset=['var3', 'var5', 'var4', 'share_new_geo'])
    print(f"   Observations with complete data: {len(complete_df):,}")
    
    if len(complete_df) > 100:
        # Simple correlation with var3
        corr = complete_df[['share_new_geo', 'var3']].corr()
        print(f"\n   Correlation(share_new_geo, var3): {corr.iloc[0,1]:.3f}")
        
        # Group by var3 values
        by_var3 = complete_df.groupby('var3')['share_new_geo'].agg(['mean', 'count'])
        print("\n   Share new geography by var3 (remote×covid):")
        print(by_var3)
        
        # Simple correlation analysis
        print("\n   Correlation matrix:")
        corr_vars = ['share_new_geo', 'var3', 'var5', 'var4', 'remote', 'teleworkable']
        corr_df = complete_df[[v for v in corr_vars if v in complete_df.columns]]
        print(corr_df.corr().round(3).loc['share_new_geo'])
    
    # Temporal trends
    print("\n9. Temporal Trends:")
    analysis_df['year'] = (analysis_df['yh_int'] / 2).astype(int)
    
    # Overall trend
    by_year = analysis_df.groupby('year')['share_new_geo'].mean()
    print("\n   Average share by year:")
    for year, share in by_year.items():
        print(f"     {int(year)}: {share:.3f}")
    
    # By remote status
    if 'remote' in analysis_df.columns:
        pivot = analysis_df.pivot_table(
            values='share_new_geo',
            index='year',
            columns='remote',
            aggfunc='mean'
        )
        print("\n   By year and remote status:")
        print(pivot)
    
    # Save analysis dataset
    print("\n10. Saving analysis dataset...")
    output_file = PROC / "firm_panel_with_geo_analysis.csv"
    analysis_df.to_csv(output_file, index=False)
    print(f"    Saved to: {output_file}")
    
    # Create summary for Stata
    print("\n" + "="*70)
    print("SUMMARY FOR STATA REGRESSION")
    print("="*70)
    print(f"\nData is ready for Stata analysis:")
    print(f"  - File: firm_panel_with_geo_analysis.csv")
    print(f"  - Observations: {len(analysis_df):,}")
    print(f"  - Key outcome: share_new_geo")
    print(f"  - Treatment: var3 (remote×covid)")
    print(f"  - Instruments: var6, var7")
    
    print("\nSuggested Stata commands:")
    print("  import delimited 'data/clean/firm_panel_with_geo_analysis.csv', clear")
    print("  ivreghdfe share_new_geo (var3 var5 = var6 var7) var4, ///")
    print("      absorb(firm_id yh) vce(cluster firm_id)")
    
    return analysis_df

if __name__ == "__main__":
    df = main()