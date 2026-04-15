#!/usr/bin/env python3
"""
Test composition calculations on a small sample to verify logic
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

# Create results directory if needed
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

print("Testing composition logic on small sample...")

# Test 1: Check LinkedIn panel structure
print("\n1. Checking LinkedIn panel structure:")
df_sample = pd.read_csv(DATA_DIR / "linkedin_panel_pandas.csv", nrows=1000)
print(f"Columns: {df_sample.columns.tolist()}")
print(f"Sample data:\n{df_sample.head()}")
print(f"Year-half range: {df_sample['yh'].min()} to {df_sample['yh'].max()}")

# Test 2: Check firm_soc_panel structure
print("\n2. Checking firm_soc_panel structure:")
df_soc = pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv", nrows=1000)
print(f"Columns: {df_soc.columns.tolist()}")
print(f"SOC4 sample: {df_soc['soc4'].value_counts().head()}")

# Test 3: Calculate composition changes for a few firms
print("\n3. Testing composition calculation logic:")

# Get a few firms with data in both periods
firms_sample = df_soc[df_soc['yh'].isin([4023, 4032])]['companyname'].value_counts()
test_firms = firms_sample[firms_sample >= 2].index[:5].tolist()
print(f"Test firms: {test_firms}")

# Calculate changes for test firms
test_data = df_soc[df_soc['companyname'].isin(test_firms)]

# Pre-COVID (2019 H2 = 4023)
pre_covid = test_data[test_data['yh'] == 4023].groupby(['companyname', 'soc4'])['headcount'].sum()
print(f"\nPre-COVID counts:\n{pre_covid.head(10)}")

# Post-COVID (2020 H2 = 4032)  
post_covid = test_data[test_data['yh'] == 4032].groupby(['companyname', 'soc4'])['headcount'].sum()
print(f"\nPost-COVID counts:\n{post_covid.head(10)}")

# Calculate % changes
changes = []
for (company, soc) in set(list(pre_covid.index) + list(post_covid.index)):
    pre = pre_covid.get((company, soc), 0)
    post = post_covid.get((company, soc), 0)
    
    if pre > 0:
        pct_change = 100 * (post - pre) / pre
    elif post > 0:
        pct_change = 100  # New role
    else:
        continue  # Skip if no employees in either period
        
    changes.append({
        'company': company,
        'soc4': soc,
        'pre': pre,
        'post': post,
        'pct_change': pct_change
    })

df_changes = pd.DataFrame(changes)
print(f"\nComposition changes:\n{df_changes}")

# Test 4: Check if we have seniority data
print("\n4. Checking for seniority data:")
if 'seniority_levels' in df_soc.columns:
    print(f"Seniority levels range: {df_soc['seniority_levels'].min()} to {df_soc['seniority_levels'].max()}")
    print(f"Seniority distribution:\n{df_soc['seniority_levels'].value_counts().head()}")
else:
    print("No seniority_levels column in firm_soc_panel")
    
# Test 5: Check firm panel for seniority
try:
    df_firm = pd.read_stata(DATA_DIR / "firm_panel.dta", convert_categoricals=False, iterator=True)
    chunk = df_firm.read(nrows=1000)
    print(f"\n5. Firm panel columns: {chunk.columns.tolist()}")
    if 'seniority_levels' in chunk.columns:
        print(f"Firm panel seniority: {chunk['seniority_levels'].describe()}")
except Exception as e:
    print(f"Could not read firm_panel.dta: {e}")

print("\nTest complete!")