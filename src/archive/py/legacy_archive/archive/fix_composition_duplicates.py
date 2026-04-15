#!/usr/bin/env python3
"""
Fix duplicate columns in composition data
"""

import pandas as pd

# Load the data
print("Loading composition data with duplicates...")
df = pd.read_csv('results/raw/composition_precovid_2019.csv')

print(f"Original columns ({len(df.columns)}): {list(df.columns)}")

# Identify duplicate column names
duplicate_cols = []
seen = set()
for col in df.columns:
    base_name = col.split('.')[0]  # Remove .1, .2, .3 suffixes
    if base_name in seen and 'level' in col:
        duplicate_cols.append(col)
    seen.add(base_name)

print(f"\nDuplicate columns to remove: {duplicate_cols}")

# Keep only the first occurrence of each column
df_clean = df.loc[:, ~df.columns.duplicated()]

print(f"\nCleaned columns ({len(df_clean.columns)}): {list(df_clean.columns)}")

# Verify the sums
role_cols = [col for col in df_clean.columns if 'share_2019' in col and 'level' not in col]
level_cols = [col for col in df_clean.columns if 'level' in col and 'share' in col]

role_sum = df_clean[role_cols].sum(axis=1)
level_sum = df_clean[level_cols].sum(axis=1)

print(f"\nVerification:")
print(f"Role shares sum: mean={role_sum.mean():.1f}%, std={role_sum.std():.1f}%")
print(f"Level shares sum: mean={level_sum.mean():.1f}%, std={level_sum.std():.1f}%")

# Save cleaned version
df_clean.to_csv('results/raw/composition_precovid_2019_clean.csv', index=False)
print("\nSaved cleaned data to: results/raw/composition_precovid_2019_clean.csv")

# Also overwrite the original
df_clean.to_csv('results/raw/composition_precovid_2019.csv', index=False)
print("Overwrote original file with clean version")

# Show final summary
print(f"\nFinal dataset:")
print(f"- Companies: {len(df_clean):,}")
print(f"- Variables: {len(df_clean.columns)}")
print(f"\nRole variables: {sorted(role_cols)}")
print(f"\nSeniority variables: {sorted(level_cols)}")