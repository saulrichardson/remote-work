#!/usr/bin/env python3
"""
Export LinkedIn panel data to CSV for Stata verification of geographic expansion logic.
"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"

# Load LinkedIn panel
print("Loading LinkedIn panel...")
df = pd.read_parquet(PROC / "linkedin_panel.parquet")

# Filter to post-2019
df_post = df[df['yh'] >= 4040].copy()

# Export for Stata
output_file = PROC / "linkedin_panel_post2019_for_verification.csv"
df_post.to_csv(output_file, index=False)
print(f"Exported {len(df_post):,} rows to {output_file}")

# Also show summary
print("\nSummary of post-2019 data:")
print(f"Firms: {df_post['companyname'].nunique():,}")
print(f"Time periods: {df_post['yh'].nunique()}")
print(f"Total joins: {df_post['joins'].sum():,}")