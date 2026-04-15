#!/usr/bin/env python3
"""
Check if remote workers are properly handled in geographic expansion.
Remote workers should NOT count as geographic expansion since they don't
represent physical presence in a new location.
"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

print("="*70)
print("CHECKING REMOTE WORKER HANDLING")
print("="*70)

# Load enriched MSA to check for remote/empty designations
msa_df = pd.read_csv(PROC / "enriched_msa.csv")
print(f"\n1. Checking MSA file for remote indicators...")
print(f"   Total MSAs: {len(msa_df)}")

# Check for common remote indicators
remote_indicators = ['remote', 'empty', 'virtual', 'distributed', 'anywhere']
for indicator in remote_indicators:
    matches = msa_df['msa'].str.lower().str.contains(indicator, na=False)
    if matches.any():
        print(f"   Found '{indicator}' in MSA names:")
        print(msa_df[matches][['msa', 'cbsacode']])

# Check for unusual CBSA codes
print(f"\n2. Checking for unusual CBSA codes...")
print(f"   CBSA range: {msa_df['cbsacode'].min()} to {msa_df['cbsacode'].max()}")

# Standard CBSA codes are 5 digits, typically 10000-49999
unusual = msa_df[(msa_df['cbsacode'] < 10000) | (msa_df['cbsacode'] >= 50000)]
if len(unusual) > 0:
    print(f"   Found {len(unusual)} unusual CBSA codes:")
    print(unusual[['msa', 'cbsacode']])
else:
    print("   All CBSA codes in standard range (10000-49999)")

# Load firm panel to check remote variable
print(f"\n3. Checking firm panel for remote designation...")
firm_panel = pd.read_csv(PROC / "firm_panel_full_with_geography.csv", nrows=1000)
if 'remote' in firm_panel.columns:
    print("   'remote' column exists in firm panel")
    print(f"   Remote values: {firm_panel['remote'].value_counts().to_dict()}")
else:
    print("   No 'remote' column in firm panel")

# Check geographic expansion calculation
print(f"\n4. Analyzing geographic expansion metrics...")
geo_df = pd.read_csv(PROC / "firm_geographic_expansion.csv")

print(f"   Firms: {geo_df['firm'].nunique()}")
print(f"   Average share in new geography: {geo_df['share_new_geo'].mean():.1%}")

# Check if any firms have 100% new geography (suspicious for remote-heavy firms)
all_new = geo_df[geo_df['share_new_geo'] == 1.0]
if len(all_new) > 0:
    print(f"\n   Found {len(all_new)} firm-periods with 100% new geography")
    print("   Sample firms with 100% new geography:")
    print(all_new.head(10)[['firm', 'yh', 'total_hires', 'n_new_locations']])

print("\n" + "="*70)
print("IMPLICATIONS:")
print("="*70)
print("""
If remote workers are included in the data but not properly flagged:
1. They may be assigned to arbitrary CBSAs (e.g., home location)
2. This would incorrectly count them as "geographic expansion"
3. The treatment effect we see (-15%) might be biased

Potential solutions:
1. Exclude workers in CBSAs with very few employees (likely remote)
2. Use occupation-based filters (exclude typically remote jobs)
3. Validate against firms known to be fully remote
""")

# Check a known remote-first company if in data
remote_firms = ['GitLab', 'Automattic', 'Buffer', 'Zapier', 'InVision']
print(f"\nChecking known remote-first companies...")
for firm in remote_firms:
    matches = geo_df[geo_df['firm'].str.lower().str.contains(firm.lower(), na=False)]
    if len(matches) > 0:
        print(f"\n{firm} found in data:")
        print(f"  Average share new geo: {matches['share_new_geo'].mean():.1%}")
        print(f"  Number of new locations: {matches['n_new_locations'].mean():.0f}")