#!/usr/bin/env python3
"""
Explore SOC codes to understand roles better
"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"

# Load SOC crosswalk if available
print("Exploring SOC codes and their meanings...\n")

# Sample the data to get most common SOCs
df = pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv", nrows=100000)

# Get top SOC4 codes by employment
soc_counts = df.groupby('soc4')['headcount'].sum().sort_values(ascending=False)
top_socs = soc_counts.head(20)

print("Top 20 SOC4 codes by employment:")
print(top_socs)

# Common SOC mappings (based on BLS SOC structure)
soc_names = {
    '1110': 'Chief Executives',
    '1120': 'General and Operations Managers',
    '1130': 'Legislators',
    '1191': 'Other Management Occupations',
    '1311': 'Computer and Information Systems Managers',
    '1320': 'Finance Managers',
    '1330': 'Marketing Managers',
    '1340': 'Sales Managers',
    '1511': 'Computer Systems Analysts',
    '1512': 'Software Developers',
    '1520': 'Database Administrators',
    '1721': 'Industrial Engineers',
    '2720': 'Postsecondary Teachers',
    '2730': 'Elementary and Middle School Teachers',
    '2740': 'Secondary School Teachers',
    '3730': 'Police and Detectives',
    '3990': 'Other Protective Service Workers',
    '4130': 'Social and Human Service Assistants',
    '4190': 'Miscellaneous Community and Social Service',
    '4310': 'Supervisors of Office Workers',
    '4330': 'Bookkeeping and Accounting Clerks',
    '4520': 'Insurance Claims Clerks',
    '4721': 'Couriers and Messengers',
    '5120': 'Bookkeepers',
    '5191': 'Other Financial Specialists',
    '5330': 'Education and Training Workers'
}

print("\nSOC codes with descriptions:")
for soc in top_socs.index[:20]:
    name = soc_names.get(str(soc), "Unknown")
    count = top_socs[soc]
    print(f"{soc}: {name} ({count:,} employees)")

# Check year-half conversion
print("\nYear-half examples:")
yh_examples = df['yh'].unique()[:10]
for yh in sorted(yh_examples):
    year = 1960 + (yh - 1) // 2
    half = 'H1' if (yh - 1) % 2 == 0 else 'H2'
    print(f"yh={yh} -> {year} {half}")

# Identify pre/post COVID periods
print("\nKey periods:")
print("Pre-COVID: 2019 H2 = yh(2019,2) = 4023")
print("Post-COVID: 2020 H2 - 2021 H1 = yh(2020,2) to yh(2021,1) = 4032-4033")