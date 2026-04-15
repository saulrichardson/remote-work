#!/usr/bin/env python3
"""Check company name formats across datasets"""

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

# Check firm panel
print("Checking firm_panel company names...")
df_firm = pd.read_stata(DATA_DIR / "firm_panel.dta", columns=['companyname'], iterator=True)
chunk = df_firm.read(nrows=100)
print("Sample names:", chunk['companyname'].head(10).tolist())

# Check SOC composition
print("\nChecking SOC composition company names...")
df_comp = pd.read_csv(RESULTS_DIR / "firm_soc_composition.csv", nrows=10)
print("Sample names:", df_comp['companyname'].head(10).tolist())

# Check firm_soc_panel
print("\nChecking firm_soc_panel company names...")
df_soc = pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv", nrows=100)
print("Sample names:", df_soc['companyname'].unique()[:10].tolist())

# Check for case differences
print("\nChecking if names differ by case...")
firm_names_lower = set([n.lower() for n in chunk['companyname'].tolist()])
comp_names_lower = set([n.lower() for n in df_comp['companyname'].tolist()])
overlap = firm_names_lower.intersection(comp_names_lower)
print(f"Overlap when lowercased: {len(overlap)} firms")