#!/usr/bin/env python3
"""
Create binary composition variables (high/low based on median splits)
"""

import pandas as pd
import numpy as np

# Load the composition data
print("Loading composition data...")
df = pd.read_csv('results/raw/composition_precovid_2019.csv')

# Create binary variables based on median splits
role_vars = ['engineer_share_2019', 'sales_share_2019', 'finance_share_2019', 
             'marketing_share_2019', 'admin_share_2019', 'operations_share_2019', 
             'scientist_share_2019']
             
seniority_vars = ['level1_share_2019', 'level2_share_2019', 'level3_share_2019', 
                  'level4_share_2019']

# Calculate medians and create binary variables
print("\nCreating binary variables based on median splits:")
print("-" * 60)

for var in role_vars + seniority_vars:
    median_val = df[var].median()
    binary_var = var.replace('_share_', '_high_')
    df[binary_var] = (df[var] > median_val).astype(int)
    
    # Report statistics
    pct_high = df[binary_var].mean() * 100
    print(f"{var}: median={median_val:.1f}%, high={pct_high:.1f}%")

# Also create some meaningful cutoffs (e.g., >20% for roles)
print("\nCreating additional binary variables with meaningful cutoffs:")
print("-" * 60)

# High engineer/sales firms (>20% threshold)
df['engineer_high20_2019'] = (df['engineer_share_2019'] > 20).astype(int)
df['sales_high20_2019'] = (df['sales_share_2019'] > 20).astype(int)

print(f"engineer_high20_2019: {df['engineer_high20_2019'].mean()*100:.1f}% of firms")
print(f"sales_high20_2019: {df['sales_high20_2019'].mean()*100:.1f}% of firms")

# Tech-focused firms (high engineer OR scientist)
df['tech_focused_2019'] = ((df['engineer_share_2019'] > df['engineer_share_2019'].median()) | 
                           (df['scientist_share_2019'] > df['scientist_share_2019'].median())).astype(int)

# Customer-focused firms (high sales OR marketing)
df['customer_focused_2019'] = ((df['sales_share_2019'] > df['sales_share_2019'].median()) | 
                               (df['marketing_share_2019'] > df['marketing_share_2019'].median())).astype(int)

# Top-heavy firms (high level 3 + level 4)
df['top_heavy_2019'] = ((df['level3_share_2019'] + df['level4_share_2019']) > 
                        (df['level3_share_2019'] + df['level4_share_2019']).median()).astype(int)

# Bottom-heavy firms (high level 1)
df['bottom_heavy_2019'] = (df['level1_share_2019'] > df['level1_share_2019'].median()).astype(int)

print(f"\ntech_focused_2019: {df['tech_focused_2019'].mean()*100:.1f}% of firms")
print(f"customer_focused_2019: {df['customer_focused_2019'].mean()*100:.1f}% of firms")
print(f"top_heavy_2019: {df['top_heavy_2019'].mean()*100:.1f}% of firms")
print(f"bottom_heavy_2019: {df['bottom_heavy_2019'].mean()*100:.1f}% of firms")

# Save the data with binary variables
df.to_csv('results/raw/composition_precovid_2019_binary.csv', index=False)
print(f"\nSaved binary composition data to: results/raw/composition_precovid_2019_binary.csv")
print(f"Total variables: {len(df.columns)}")

# Convert to Stata format
df.to_stata('results/raw/composition_precovid_2019_binary.dta', write_index=False)
print(f"Also saved as: results/raw/composition_precovid_2019_binary.dta")