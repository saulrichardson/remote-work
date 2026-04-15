#!/usr/bin/env python3
"""
Explore LinkedIn data columns to identify fields needed for composition analysis
"""

import pandas as pd
import duckdb

# Connect to DuckDB
con = duckdb.connect(':memory:')

# Read first 1000 rows to explore
print("Loading sample of LinkedIn data...")
df_sample = pd.read_csv(
    '/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv',
    nrows=1000
)

print("\nColumn names and types:")
for col in df_sample.columns:
    print(f"{col}: {df_sample[col].dtype}")

print("\n\nKey columns for composition analysis:")
print("-" * 60)

# Check company name columns
print("\n1. Company identifiers:")
print(f"   company: {df_sample['company'].iloc[0:3].tolist()}")
print(f"   company_priname: {df_sample['company_priname'].iloc[0:3].tolist()}")
print(f"   companyname: {df_sample['companyname'].iloc[0:3].tolist()}")

# Check SOC code columns  
print("\n2. SOC/Role columns:")
print(f"   soc6d: {df_sample['soc6d'].iloc[0:3].tolist()}")
print(f"   soc_2010: {df_sample['soc_2010'].iloc[0:3].tolist()}")
print(f"   role_k7: {df_sample['role_k7'].iloc[0:3].tolist()}")

# Check seniority
print("\n3. Seniority column:")
print(f"   Unique values (first 10): {df_sample['seniority'].value_counts().head(10).to_dict()}")

# Check dates
print("\n4. Date columns:")
print(f"   start_date: {df_sample['start_date'].iloc[0:3].tolist()}")
print(f"   end_date: {df_sample['end_date'].iloc[0:3].tolist()}")

# Check which columns have good coverage
print("\n5. Column coverage (% non-null):")
coverage = (df_sample.count() / len(df_sample) * 100).sort_values(ascending=False)
for col, pct in coverage.items():
    if col in ['user_id', 'company_priname', 'companyname', 'seniority', 'soc_2010', 'soc6d', 'start_date', 'end_date']:
        print(f"   {col}: {pct:.1f}%")

con.close()