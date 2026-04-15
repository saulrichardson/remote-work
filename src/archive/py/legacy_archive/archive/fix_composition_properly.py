#!/usr/bin/env python3
"""
Properly fix the composition data by removing all duplicate columns
"""

import pandas as pd

# Load the data
print("Loading composition data...")
df = pd.read_csv('results/raw/composition_precovid_2019.csv')

# Keep only non-duplicate columns
columns_to_keep = [
    'companyname',
    'companyname_lower', 
    'total_employees_2019',
    # Role shares
    'admin_share_2019',
    'engineer_share_2019',
    'finance_share_2019',
    'marketing_share_2019',
    'operations_share_2019',
    'sales_share_2019',
    'scientist_share_2019',
    # Seniority shares - only keep the first occurrence
    'level1_share_2019',
    'level2_share_2019',
    'level3_share_2019',
    'level4_share_2019'
]

# Select only these columns
df_clean = df[columns_to_keep].copy()

print(f"Cleaned data: {len(df_clean)} companies, {len(df_clean.columns)} columns")
print(f"Columns: {list(df_clean.columns)}")

# Verify the sums
role_cols = ['admin_share_2019', 'engineer_share_2019', 'finance_share_2019', 
             'marketing_share_2019', 'operations_share_2019', 'sales_share_2019', 
             'scientist_share_2019']
level_cols = ['level1_share_2019', 'level2_share_2019', 'level3_share_2019', 'level4_share_2019']

role_sum = df_clean[role_cols].sum(axis=1)
level_sum = df_clean[level_cols].sum(axis=1)

print(f"\nData quality check:")
print(f"- Role shares sum: mean={role_sum.mean():.1f}%, std={role_sum.std():.1f}%")
print(f"- Level shares sum: mean={level_sum.mean():.1f}%, std={level_sum.std():.1f}%")

# Save the clean version
df_clean.to_csv('results/raw/composition_precovid_2019.csv', index=False)
print("\nSaved clean data to: results/raw/composition_precovid_2019.csv")

# Show summary statistics
print("\nComposition summary:")
print("-" * 50)
print("Role shares (% of companies with >20% in role):")
for col in role_cols:
    pct = (df_clean[col] > 20).sum() / len(df_clean) * 100
    print(f"  {col}: {pct:.1f}%")

print("\nSeniority distribution (mean %):")
for col in level_cols:
    print(f"  {col}: {df_clean[col].mean():.1f}%")

print("\nTop companies by size:")
print(df_clean.nlargest(10, 'total_employees_2019')[['companyname', 'total_employees_2019', 'engineer_share_2019', 'sales_share_2019']])