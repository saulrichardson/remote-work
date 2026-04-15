#!/usr/bin/env python3
"""
Merge geographic expansion with FULL firm panel (keeping all 41,980 obs).
Sets pre-period geographic expansion to 0 (since 2019 is the baseline).
This matches the approach used in other studies.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

def main():
    print("="*70)
    print("Merging Geographic Expansion with FULL Panel")
    print("="*70)
    
    # 1. Load FULL firm panel
    print("\n1. Loading full firm panel...")
    panel = pd.read_stata(PROC / "firm_panel.dta")
    print(f"   Loaded: {len(panel):,} observations")
    print(f"   Firms: {panel['companyname'].nunique():,}")
    print(f"   Pre-COVID: {(panel['covid'] == 0).sum():,}")
    print(f"   Post-COVID: {(panel['covid'] == 1).sum():,}")
    
    # Standardize company names
    panel['companyname_lower'] = panel['companyname'].str.lower()
    
    # 2. Load geographic expansion (post-period only)
    print("\n2. Loading geographic expansion data...")
    geo = pd.read_csv(PROC / "firm_geographic_expansion.csv")
    geo['companyname_lower'] = geo['firm'].str.lower()
    print(f"   Loaded: {len(geo):,} firm-periods (post-2019 only)")
    
    # Prepare for merge - rename columns
    geo_merge = geo[['companyname_lower', 'yh', 'share_new_geo', 
                     'new_geo_hires', 'total_hires', 'n_new_locations']].copy()
    
    # Handle yh type mismatch
    if str(panel['yh'].dtype).startswith('datetime'):
        # Convert datetime to integer half-year
        panel['year'] = panel['yh'].dt.year
        panel['half'] = panel['yh'].apply(lambda x: 2 if x.month == 7 else 1)
        panel['yh_int'] = panel['year'] * 2 + panel['half'] - 1
    else:
        panel['yh_int'] = panel['yh'].astype(int)
    
    geo_merge['yh_int'] = geo_merge['yh'].astype(int)
    
    # 3. Merge (keeping ALL panel observations)
    print("\n3. Merging datasets...")
    merged = panel.merge(
        geo_merge[['companyname_lower', 'yh_int', 'share_new_geo', 
                   'new_geo_hires', 'total_hires', 'n_new_locations']],
        on=['companyname_lower', 'yh_int'],
        how='left',  # Keep ALL panel obs
        indicator=True
    )
    
    print(f"\n   Merge results:")
    print(f"     Total obs: {len(merged):,}")
    print(f"     With geo data: {(merged['_merge'] == 'both').sum():,}")
    print(f"     Without geo data: {(merged['_merge'] == 'left_only').sum():,}")
    
    # 4. KEY STEP: Set pre-period values
    print("\n4. Setting pre-period values...")
    
    # For pre-COVID, geographic expansion is 0 by definition
    # (can't have "new" locations relative to 2019 before 2019)
    pre_mask = merged['covid'] == 0
    merged.loc[pre_mask, 'share_new_geo'] = 0
    merged.loc[pre_mask, 'n_new_locations'] = 0
    merged.loc[pre_mask, 'new_geo_hires'] = 0
    
    # For post-COVID firms with no hiring, also set to 0
    post_no_hire = (merged['covid'] == 1) & (merged['total_hires'].isna() | (merged['total_hires'] == 0))
    merged.loc[post_no_hire, 'share_new_geo'] = 0
    merged.loc[post_no_hire, 'n_new_locations'] = 0
    
    print(f"   Pre-period obs set to 0: {pre_mask.sum():,}")
    print(f"   Post-period no-hire set to 0: {post_no_hire.sum():,}")
    
    # 5. Create additional variables
    merged['has_new_geo'] = (merged['n_new_locations'] > 0).astype(int)
    merged['log_new_locations'] = np.log1p(merged['n_new_locations'].fillna(0))
    
    # 6. Summary statistics
    print("\n5. Summary Statistics:")
    
    # Overall
    print(f"\n   Share new geography by period:")
    by_covid = merged.groupby('covid')['share_new_geo'].agg(['mean', 'std', 'count'])
    print(by_covid)
    
    # Check treatment balance
    if 'var3' in merged.columns:
        print(f"\n   Observations by treatment (var3):")
        treat_counts = merged.groupby(['covid', 'var3']).size().unstack(fill_value=0)
        print(treat_counts)
    
    # 7. Save full panel with geography
    output_file = PROC / "firm_panel_full_with_geography.csv"
    merged.to_csv(output_file, index=False)
    print(f"\n6. Saved to: {output_file}")
    
    # Also save as Stata
    try:
        output_dta = PROC / "firm_panel_full_with_geography.dta"
        # Clean strings for Stata
        for col in merged.select_dtypes(include=['object']).columns:
            merged[col] = merged[col].astype(str).replace('nan', '')
        merged.to_stata(output_dta, write_index=False, version=117)
        print(f"   Also saved as: {output_dta}")
    except Exception as e:
        print(f"   Could not save Stata file: {e}")
    
    print("\n" + "="*70)
    print("COMPLETE: Full panel with geography ready for analysis")
    print(f"Total observations: {len(merged):,} (matching original panel)")
    print("="*70)
    
    return merged

if __name__ == "__main__":
    df = main()