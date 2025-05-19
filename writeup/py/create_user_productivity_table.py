#!/usr/bin/env python3
"""
Scaffold for building the User Productivity LaTeX table.
Create a placeholder .tex under results/cleaned for manual completion.
"""
from pathlib import Path
import pandas as pd
# -----------------------------------------------------------------------------
# 1) Setup project paths
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
# PROJECT_ROOT should point to the project root, two levels above this script
PROJECT_ROOT = HERE.parents[2]

# -----------------------------------------------------------------------------
# 2) Define file paths
# -----------------------------------------------------------------------------
SPEC = "user_productivity"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
INPUT_BASE = RAW_DIR / SPEC / "consolidated_results.csv"
INPUT_ALT = RAW_DIR / f"{SPEC}_alternative_fe" / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}.tex"

print(INPUT_BASE)
print(INPUT_ALT)




# -----------------------------------------------------------------------------
# 7) Write out .tex
# -----------------------------------------------------------------------------
OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")