#!/usr/bin/env python3
"""
Merge three-way hiring classification with FULL firm panel for regression analysis.

This script merges the three-way hiring metrics (legacy MSA, new MSA, remote)
with the complete firm panel (41,980 observations) to enable testing whether
remote work substitutes for or complements geographic expansion.

For pre-2020 periods (before our classification baseline):
- share_legacy_msa = 1.0 (all hires are in "existing" locations by definition)
- share_new_msa = 0 (no "new" locations before baseline)
- share_remote = 0 (no remote classification before baseline)
- total_dispersion = 0 (no dispersion before baseline)

Output:
-------
data/clean/firm_panel_threeway_geography.csv
    Ready for Stata IV regression analysis

Usage:
------
python py/merge_threeway_with_firm_panel.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

# Input files
FIRM_PANEL = PROC / "firm_panel.dta"
THREEWAY_METRICS = PROC / "firm_threeway_hiring_metrics.csv"
GEOGRAPHY_EXPANSION = PROC / "firm_geographic_expansion.csv"  # For comparison

# Output
OUTPUT = PROC / "firm_panel_threeway_geography.csv"


def main():
    print("="*70)
    print("Merging Three-Way Classification with Full Firm Panel")
    print("="*70)
    
    # 1. Load full firm panel
    print("\n1. Loading full firm panel...")
    panel = pd.read_stata(FIRM_PANEL)
    print(f"   Loaded: {len(panel):,} observations")
    print(f"   Firms: {panel['companyname'].nunique():,}")
    print(f"   Pre-COVID (covid=0): {(panel['covid'] == 0).sum():,}")
    print(f"   Post-COVID (covid=1): {(panel['covid'] == 1).sum():,}")
    
    # Standardize company names
    panel['companyname_lower'] = panel['companyname'].str.lower()
    
    # 2. Load three-way hiring metrics
    print("\n2. Loading three-way hiring metrics...")
    threeway = pd.read_csv(THREEWAY_METRICS)
    threeway['companyname_lower'] = threeway['firm'].str.lower()
    print(f"   Loaded: {len(threeway):,} firm-periods (post-2019 only)")
    print(f"   Firms: {threeway['firm'].nunique():,}")
    
    # Prepare for merge - select key columns
    threeway_merge = threeway[[
        'companyname_lower', 'yh',
        'share_legacy_msa', 'share_new_msa', 'share_remote',
        'total_dispersion', 'remote_substitution_rate',
        'total_hires', 'legacy_msa_hires', 'new_msa_hires', 'remote_hires',
        'n_new_locations'
    ]].copy()
    
    # Handle yh type mismatch if needed
    if str(panel['yh'].dtype).startswith('datetime'):
        # Convert datetime to integer half-year
        panel['year'] = panel['yh'].dt.year
        # Half = 1 if months 1-6, else 2
        panel['half'] = panel['yh'].dt.month.apply(lambda m: 1 if m <= 6 else 2)
        panel['yh_int'] = panel['year'] * 2 + (panel['half'] - 1)
    else:
        panel['yh_int'] = panel['yh'].astype(int)
    
    threeway_merge['yh_int'] = threeway_merge['yh'].astype(int)
    
    # 3. Merge (keeping ALL panel observations)
    print("\n3. Merging datasets...")
    merged = panel.merge(
        threeway_merge.drop('yh', axis=1),
        on=['companyname_lower', 'yh_int'],
        how='left',
        indicator=True
    )
    
    print(f"\n   Merge results:")
    print(f"     Total obs: {len(merged):,}")
    print(f"     With threeway data: {(merged['_merge'] == 'both').sum():,}")
    print(f"     Without threeway data: {(merged['_merge'] == 'left_only').sum():,}")
    
    # 4. Set pre-period values
    print("\n4. Setting pre-period values...")
    
    # For pre-COVID periods, set baseline values
    pre_mask = merged['covid'] == 0
    
    # Pre-2020: all hires are in "existing" locations by definition
    merged.loc[pre_mask, 'share_legacy_msa'] = 1.0
    merged.loc[pre_mask, 'share_new_msa'] = 0.0
    merged.loc[pre_mask, 'share_remote'] = 0.0
    merged.loc[pre_mask, 'total_dispersion'] = 0.0
    merged.loc[pre_mask, 'remote_substitution_rate'] = 0.0
    merged.loc[pre_mask, 'n_new_locations'] = 0
    
    # Post-COVID periods with no hiring data: leave shares as NA (no imputation)
    post_no_data = (merged['covid'] == 1) & (merged['total_hires'].isna())
    print(f"   Pre-period obs set to baseline: {pre_mask.sum():,}")
    print(f"   Post-period with no hires (left as NA): {post_no_data.sum():,}")
    
    # 5. Load original geographic expansion for comparison
    print("\n5. Loading original geographic expansion for comparison...")
    geo_orig = pd.read_csv(GEOGRAPHY_EXPANSION)
    geo_orig['companyname_lower'] = geo_orig['firm'].str.lower()
    geo_orig_merge = geo_orig[['companyname_lower', 'yh', 'share_new_geo']].copy()
    geo_orig_merge['yh_int'] = geo_orig_merge['yh'].astype(int)
    
    # Merge original metric
    merged = merged.merge(
        geo_orig_merge[['companyname_lower', 'yh_int', 'share_new_geo']],
        on=['companyname_lower', 'yh_int'],
        how='left',
        suffixes=('', '_orig')
    )
    
    # Set pre-period to 0 for original metric too
    merged.loc[pre_mask, 'share_new_geo'] = 0.0
    
    # 6. Create additional variables
    print("\n6. Creating additional analysis variables...")
    
    # Binary indicators
    merged['has_remote'] = (merged['share_remote'] > 0).astype(int)
    merged['has_new_msa'] = (merged['share_new_msa'] > 0).astype(int)
    merged['has_dispersion'] = (merged['total_dispersion'] > 0).astype(int)
    
    # Log transformations
    merged['log_new_locations'] = np.log1p(merged['n_new_locations'].fillna(0))
    
    # Non-breaking hygiene: flag no-hire periods for downstream filtering
    merged['no_hire'] = ((merged['total_hires'].fillna(0) <= 0).astype(int))
    
    # Interaction for substitution test
    merged['new_msa_x_remote'] = merged['share_new_msa'] * merged['share_remote']
    
    # 7. Summary statistics
    print("\n7. Summary Statistics:")
    
    # Overall by period
    print(f"\n   Three-way shares by period:")
    print("   " + "-"*60)
    by_covid = merged.groupby('covid')[['share_legacy_msa', 'share_new_msa', 'share_remote', 'total_dispersion']].agg(['mean', 'std'])
    print(by_covid)
    
    # Treatment group comparison (post-period only)
    if 'var3' in merged.columns:
        post_merged = merged[merged['covid'] == 1].copy()
        print(f"\n   Post-period by treatment (var3):")
        print("   " + "-"*60)
        by_treatment = post_merged.groupby('var3')[['share_legacy_msa', 'share_new_msa', 'share_remote', 'total_dispersion']].mean()
        print(by_treatment)
        
        # Calculate differences
        if len(by_treatment) >= 2:
            diff = by_treatment.loc[1] - by_treatment.loc[0] if 1 in by_treatment.index and 0 in by_treatment.index else None
            if diff is not None:
                print(f"\n   Treatment effect (var3=1 vs var3=0):")
                print("   " + "-"*60)
                for col in diff.index:
                    print(f"     {col:20s}: {diff[col]:+.4f}")
    
    # 8. Validation checks
    print("\n8. Validation Checks:")
    
    # Check share consistency
    post_data = merged[merged['covid'] == 1].copy()
    post_data['share_sum'] = post_data['share_legacy_msa'] + post_data['share_new_msa'] + post_data['share_remote']
    deviation = (post_data['share_sum'] - 1.0).abs()
    
    print(f"   Share validation (post-period with data):")
    print(f"     Max deviation from 1.0: {deviation.max():.6f}")
    print(f"     Obs with >1% deviation: {(deviation > 0.01).sum()}")
    
    # Compare new_msa metrics
    comparison = merged[merged['covid'] == 1][['share_new_msa', 'share_new_geo']].dropna()
    if len(comparison) > 0:
        corr = comparison.corr().iloc[0, 1]
        diff_mean = (comparison['share_new_msa'] - comparison['share_new_geo']).mean()
        print(f"\n   New MSA metric comparison:")
        print(f"     Correlation: {corr:.4f}")
        print(f"     Mean difference: {diff_mean:.4f}")
    
    # 9. Save output
    print("\n9. Saving output...")
    
    # Drop merge indicators and temp columns
    output_cols = [col for col in merged.columns if not col.startswith('_') and col != 'companyname_lower']
    merged[output_cols].to_csv(OUTPUT, index=False)
    
    print(f"   ✓ Saved to {OUTPUT.name}")
    print(f"     Rows: {len(merged):,}")
    print(f"     Columns: {len(output_cols)}")
    
    print("\n" + "="*70)
    print("Merge complete! Ready for three-way regression analysis.")
    print("="*70)
    
    return merged


if __name__ == "__main__":
    main()
