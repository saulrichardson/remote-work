#!/usr/bin/env python3
"""
Create Pre-COVID (2019) Composition Variables using pandas for robustness
Tests on partial data first, then can run on full dataset
"""

import pandas as pd
import numpy as np
from pathlib import Path
import time
import warnings
warnings.filterwarnings('ignore')

def create_composition_variables(nrows=None):
    """
    Create pre-COVID composition variables from LinkedIn data
    
    Args:
        nrows: Number of rows to read (None for full data)
    """
    # Start timer
    start_time = time.time()
    
    print("Creating Pre-COVID Composition Variables")
    print("="*60)
    
    # Path to LinkedIn data
    linkedin_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv")
    
    # Define columns we need
    columns_needed = ['companyname', 'user_id', 'role_k7', 'seniority', 'start_date', 'end_date']
    
    # Read data
    if nrows:
        print(f"Reading first {nrows:,} rows for testing...")
    else:
        print("Reading full dataset...")
    
    try:
        df = pd.read_csv(
            linkedin_path,
            usecols=columns_needed,
            nrows=nrows,
            on_bad_lines='skip',  # Skip problematic rows
            low_memory=False
        )
    except ValueError:
        # If columns not found by name, try by position
        print("Column names not found, reading by position...")
        df = pd.read_csv(
            linkedin_path,
            usecols=[25, 2, 14, 13, 23, 24],  # positions of needed columns
            nrows=nrows,
            on_bad_lines='skip',
            low_memory=False
        )
        df.columns = columns_needed
    
    print(f"Loaded {len(df):,} rows")
    
    # Clean data
    print("\nCleaning data...")
    df = df.dropna(subset=['companyname', 'user_id', 'role_k7', 'seniority'])
    print(f"After removing nulls: {len(df):,} rows")
    
    # Convert dates
    df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
    df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')
    
    # Filter for employees active in 2019
    print("\nFiltering for employees active in 2019...")
    mask = (
        (df['end_date'] >= '2019-01-01') | df['end_date'].isna()
    ) & (
        df['start_date'].isna() | (df['start_date'] <= '2019-12-31')
    )
    df_2019 = df[mask].copy()
    print(f"Employees active in 2019: {len(df_2019):,}")
    
    # Get unique employees per company
    print("\nCalculating composition by company...")
    df_unique = df_2019.drop_duplicates(subset=['companyname', 'user_id'])
    
    # Calculate total employees per company
    company_totals = df_unique.groupby('companyname')['user_id'].count().reset_index()
    company_totals.columns = ['companyname', 'total_employees_2019']
    
    # Filter companies with at least 10 employees
    company_totals = company_totals[company_totals['total_employees_2019'] >= 10]
    print(f"Companies with 10+ employees: {len(company_totals):,}")
    
    # Calculate role composition
    print("\nCalculating role composition...")
    role_comp = df_unique.groupby(['companyname', 'role_k7'])['user_id'].count().unstack(fill_value=0)
    role_pct = role_comp.div(role_comp.sum(axis=1), axis=0) * 100
    
    # Rename columns
    role_cols = {col: f"{col.lower()}_share_2019" for col in role_pct.columns}
    role_pct = role_pct.rename(columns=role_cols)
    
    # Calculate seniority composition
    print("Calculating seniority composition...")
    sen_comp = df_unique.groupby(['companyname', 'seniority'])['user_id'].count().unstack(fill_value=0)
    sen_pct = sen_comp.div(sen_comp.sum(axis=1), axis=0) * 100
    
    # Rename columns
    sen_cols = {col: f"level{int(col)}_share_2019" for col in sen_pct.columns}
    sen_pct = sen_pct.rename(columns=sen_cols)
    
    
    # Merge all composition data
    print("\nMerging all composition variables...")
    result = company_totals.set_index('companyname')
    
    # Add role percentages
    result = result.join(role_pct, how='left')
    
    # Add seniority percentages  
    result = result.join(sen_pct, how='left')
    
    # Fill missing values with 0
    result = result.fillna(0)
    
    # Reset index
    result = result.reset_index()
    
    # Add lowercase company name for Stata merging
    result['companyname_lower'] = result['companyname'].str.lower()
    
    # Reorder columns to put companyname_lower after companyname
    cols = result.columns.tolist()
    cols.remove('companyname_lower')
    cols.insert(1, 'companyname_lower')
    result = result[cols]
    
    # Print summary statistics
    print(f"\nProcessing complete in {time.time() - start_time:.1f} seconds")
    print(f"Number of companies: {len(result):,}")
    print(f"Average employees per company: {result['total_employees_2019'].mean():.1f}")
    
    # Show distribution of key variables
    print("\nComposition Summary (mean % of workforce):")
    print("-"*40)
    
    # Print available role columns
    role_share_cols = [col for col in result.columns if 'share_2019' in col and 'level' not in col]
    for col in sorted(role_share_cols):
        print(f"{col:<30} {result[col].mean():>6.1f}%")
    
    print()
    
    # Print seniority columns
    level_cols = [col for col in result.columns if 'level' in col and 'share' in col]
    for col in sorted(level_cols):
        print(f"{col:<30} {result[col].mean():>6.1f}%")
    
    # Show sample of results
    print("\nSample Results (first 5 companies):")
    print("-"*60)
    display_cols = ['companyname', 'total_employees_2019']
    
    # Add first few composition columns
    for col in result.columns:
        if 'engineer' in col or 'sales' in col:
            display_cols.append(col)
            if len(display_cols) >= 5:
                break
    
    print(result[display_cols].head().to_string(index=False))
    
    # Data quality checks
    print("\nData Quality Checks:")
    print("-"*40)
    
    # Check role percentages sum
    role_sum = result[role_share_cols].sum(axis=1)
    print(f"Role percentages sum - Mean: {role_sum.mean():.1f}%, Std: {role_sum.std():.1f}%")
    
    # Check seniority percentages sum
    if level_cols:
        sen_sum = result[level_cols].sum(axis=1)
        print(f"Seniority percentages sum - Mean: {sen_sum.mean():.1f}%, Std: {sen_sum.std():.1f}%")
    
    # Save to CSV
    output_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/results/raw/composition_precovid_2019.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")
    
    return result

if __name__ == "__main__":
    # Test with 100k rows first
    print("Testing with 100,000 rows...")
    df_test = create_composition_variables(nrows=100000)
    
    print("\n" + "="*60)
    print("Test successful! To run on full data, use:")
    print("  df_full = create_composition_variables(nrows=None)")
    print("="*60)