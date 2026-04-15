#!/usr/bin/env python3
"""Check actual yh values in the data"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"

# Check firm_soc_panel
print("Checking yh values in firm_soc_panel...")
df = pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv", nrows=100000)
yh_counts = df['yh'].value_counts().sort_index()

print("\nYear-half distribution:")
print(yh_counts.head(20))
print("...")
print(yh_counts.tail(20))

# Try to decode the pattern
print("\nTrying to decode yh pattern:")
for yh in [4020, 4021, 4022, 4023, 4024, 4031, 4032, 4033]:
    # Assuming 4000 series starting from some base year
    base = 4000
    periods_from_base = yh - base
    year = 2010 + periods_from_base // 2
    half = 1 + periods_from_base % 2
    print(f"yh={yh} -> {year} H{half}")

# Check specific periods
print("\nLooking for 2019-2021 data:")
df_2019_2021 = df[(df['year'] >= 2019) & (df['year'] <= 2021)]
print(df_2019_2021[['year', 'yh']].drop_duplicates().sort_values(['year', 'yh']))