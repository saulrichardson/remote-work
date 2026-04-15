#!/usr/bin/env python3
"""
Verify the composition data is ready for Stata analysis
"""

import pandas as pd
import numpy as np

# Load the composition data
print("Loading composition data...")
comp_df = pd.read_csv('results/raw/composition_precovid_2019.csv')

print(f"\n1. Dataset Overview:")
print(f"   - Number of companies: {len(comp_df):,}")
print(f"   - Number of variables: {len(comp_df.columns)}")
print(f"   - Columns: {list(comp_df.columns)}")

print(f"\n2. Company name check:")
print(f"   - Has companyname: {'companyname' in comp_df.columns}")
print(f"   - Has companyname_lower: {'companyname_lower' in comp_df.columns}")
print(f"   - Sample names: {comp_df['companyname'].head(3).tolist()}")
print(f"   - Sample lower: {comp_df['companyname_lower'].head(3).tolist()}")

print(f"\n3. Size distribution:")
print(comp_df['total_employees_2019'].describe())

print(f"\n4. Role composition (% of companies with >10% in each role):")
role_cols = [col for col in comp_df.columns if 'share_2019' in col and 'level' not in col]
for col in sorted(role_cols):
    pct_above_10 = (comp_df[col] > 10).sum() / len(comp_df) * 100
    print(f"   {col}: {pct_above_10:.1f}% of companies")

print(f"\n5. Seniority distribution (mean % across companies):")
level_cols = [col for col in comp_df.columns if 'level' in col and 'share' in col]
for col in sorted(level_cols):
    print(f"   {col}: {comp_df[col].mean():.1f}%")

print(f"\n6. Data quality checks:")
# Check for missing values
missing = comp_df.isnull().sum()
if missing.sum() == 0:
    print("   ✓ No missing values")
else:
    print("   ✗ Missing values found:")
    print(missing[missing > 0])

# Check if percentages sum to 100
role_sum = comp_df[role_cols].sum(axis=1)
level_sum = comp_df[level_cols].sum(axis=1)
print(f"   - Role shares sum: mean={role_sum.mean():.1f}%, std={role_sum.std():.1f}%")
print(f"   - Level shares sum: mean={level_sum.mean():.1f}%, std={level_sum.std():.1f}%")

# Check for companies that might match firm panel
print(f"\n7. Sample of large tech companies (if present):")
tech_companies = ['google', 'microsoft', 'apple', 'amazon', 'facebook', 'meta']
for company in tech_companies:
    matches = comp_df[comp_df['companyname_lower'].str.contains(company, na=False)]
    if len(matches) > 0:
        row = matches.iloc[0]
        print(f"   {row['companyname']}: {row['total_employees_2019']:.0f} employees, "
              f"{row.get('engineer_share_2019', 0):.1f}% engineers")

print("\n✓ Data verification complete!")
print("Ready for Stata merge using 'companyname_lower'")

# Save a small sample for testing
sample_df = comp_df.head(20)
sample_df.to_csv('results/raw/composition_precovid_2019_sample.csv', index=False)
print("\nSaved 20-row sample to: results/raw/composition_precovid_2019_sample.csv")