#!/usr/bin/env python3
"""
Create a sample dataset with proper name matching for testing Stata scripts
"""

import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

print("Creating composition sample with matched names...")

# Read a sample of firm panel to get company names
print("Reading firm panel sample...")
firm_df = pd.read_stata(DATA_DIR / "firm_panel.dta", 
                       columns=['companyname', 'yh', 'growth_rate_we', 'startup', 
                               'age', 'rent', 'hhi_1000', 'covid', 'seniority_levels',
                               'total_employees'],
                       iterator=True)
firm_sample = firm_df.read(nrows=50000)
firm_sample['companyname_lower'] = firm_sample['companyname'].str.lower()

# Get unique companies
unique_firms = firm_sample['companyname_lower'].unique()
print(f"Found {len(unique_firms)} unique firms in panel sample")

# Read firm-SOC panel for these companies only
print("Processing SOC data for matched firms...")
chunks = []
for chunk in pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv",
                        usecols=['companyname', 'soc4', 'yh', 'headcount'],
                        chunksize=100000):
    # Filter to our firms
    chunk_filtered = chunk[chunk['companyname'].isin(unique_firms)]
    if len(chunk_filtered) > 0:
        chunks.append(chunk_filtered)
    
    # Stop if we have enough data
    if len(chunks) > 10:
        break

df_soc = pd.concat(chunks, ignore_index=True)
print(f"Loaded {len(df_soc)} SOC records for matched firms")

# Calculate composition changes
pre_covid_yh = 4039  # 2019 H2
post_covid_yhs = [4041, 4042]  # 2020 H2, 2021 H1

# Pre-COVID
pre_df = df_soc[df_soc['yh'] == pre_covid_yh].groupby(['companyname', 'soc4'])['headcount'].sum()

# Post-COVID average
post_df = df_soc[df_soc['yh'].isin(post_covid_yhs)].groupby(['companyname', 'soc4', 'yh'])['headcount'].sum()
post_df = post_df.groupby(['companyname', 'soc4']).mean()

# Calculate changes
merged = pd.DataFrame({
    'pre': pre_df,
    'post': post_df
}).fillna(0)

merged['pct_change'] = np.where(
    merged['pre'] > 0,
    100 * (merged['post'] - merged['pre']) / merged['pre'],
    np.where(merged['post'] > 0, 100, 0)
)

# Get top 10 SOCs for this sample
soc_totals = merged.groupby(level='soc4')['pre'].sum().sort_values(ascending=False)
top_socs = soc_totals.head(10).index.tolist()

print(f"Top 10 SOCs in sample: {top_socs}")

# Create wide format
wide_df = merged['pct_change'].unstack(level='soc4')[top_socs].fillna(0)
wide_df.columns = [f'pct_chg_soc{col}' for col in wide_df.columns]
wide_df = wide_df.reset_index()

# Ensure we use lowercase names for matching
wide_df['companyname_lower'] = wide_df['companyname']
wide_df = wide_df.drop('companyname', axis=1)

# Save
wide_df.to_csv(RESULTS_DIR / "composition_sample.csv", index=False)
wide_df.to_stata(RESULTS_DIR / "composition_sample.dta", write_index=False)

print(f"\nCreated composition data for {len(wide_df)} firms")
print("Files saved:")
print("- results/raw/composition_sample.csv")
print("- results/raw/composition_sample.dta")

# Also create a simplified seniority dataset
print("\nCreating seniority composition...")
sen_pre = firm_sample[firm_sample['yh'] == 119].groupby('companyname_lower')[['seniority_levels', 'total_employees']].first()
sen_post = firm_sample[firm_sample['yh'].isin([121, 122])].groupby('companyname_lower')[['seniority_levels', 'total_employees']].mean()

sen_df = pd.DataFrame({
    'companyname_lower': sen_pre.index,
    'sen_levels_pre': sen_pre['seniority_levels'].values,
    'emp_pre': sen_pre['total_employees'].values,
    'sen_levels_post': sen_post['seniority_levels'].reindex(sen_pre.index).values,
    'emp_post': sen_post['total_employees'].reindex(sen_pre.index).values
})

sen_df['sen_concentration_chg'] = 100 * (sen_df['sen_levels_post'] - sen_df['sen_levels_pre']) / sen_df['sen_levels_pre']
sen_df['emp_growth'] = 100 * (sen_df['emp_post'] - sen_df['emp_pre']) / sen_df['emp_pre']

# Handle infinities
sen_df.replace([np.inf, -np.inf], np.nan, inplace=True)

sen_df.to_csv(RESULTS_DIR / "seniority_sample.csv", index=False)
sen_df.to_stata(RESULTS_DIR / "seniority_sample.dta", write_index=False)

print(f"Created seniority data for {len(sen_df)} firms")
print("\nSample complete!")