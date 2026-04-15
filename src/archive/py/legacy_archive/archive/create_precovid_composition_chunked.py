#!/usr/bin/env python3
"""
Create Pre-COVID (2019) Composition Variables - Memory Efficient Chunked Version
Processes large LinkedIn data in chunks to avoid memory issues
"""

import pandas as pd
import numpy as np
from pathlib import Path
import time
import warnings
import gc
warnings.filterwarnings('ignore')

def process_in_chunks(input_path, output_path, chunksize=500000):
    """
    Process LinkedIn data in chunks to manage memory usage
    
    Args:
        input_path: Path to Scoop_workers_positions.csv
        output_path: Where to save the output CSV
        chunksize: Number of rows per chunk
    """
    start_time = time.time()
    
    print("Creating Pre-COVID Composition Variables - Chunked Version")
    print("="*60)
    print(f"Processing in chunks of {chunksize:,} rows")
    
    # Define columns we need
    columns_needed = ['companyname', 'user_id', 'role_k7', 'seniority', 'start_date', 'end_date']
    
    # Initialize storage for 2019 employees
    employees_2019 = []
    chunk_count = 0
    total_rows = 0
    
    print("\nReading and filtering data by chunks...")
    
    # Process file in chunks
    try:
        for chunk in pd.read_csv(
            input_path,
            usecols=columns_needed,
            chunksize=chunksize,
            on_bad_lines='skip',
            low_memory=False
        ):
            chunk_count += 1
            total_rows += len(chunk)
            
            # Clean chunk
            chunk = chunk.dropna(subset=['companyname', 'user_id', 'role_k7', 'seniority'])
            
            # Convert dates
            chunk['start_date'] = pd.to_datetime(chunk['start_date'], errors='coerce')
            chunk['end_date'] = pd.to_datetime(chunk['end_date'], errors='coerce')
            
            # Filter for 2019 employees
            mask = (
                (chunk['end_date'] >= '2019-01-01') | chunk['end_date'].isna()
            ) & (
                chunk['start_date'].isna() | (chunk['start_date'] <= '2019-12-31')
            )
            
            chunk_2019 = chunk[mask]
            
            if len(chunk_2019) > 0:
                employees_2019.append(chunk_2019[['companyname', 'user_id', 'role_k7', 'seniority']])
            
            # Progress report
            if chunk_count % 10 == 0:
                print(f"  Processed {total_rows:,} rows, found {sum(len(df) for df in employees_2019):,} 2019 employees")
                gc.collect()  # Force garbage collection
                
    except ValueError:
        print("Error: Could not find required columns. Please check the file format.")
        return None
    
    print(f"\nTotal rows processed: {total_rows:,}")
    
    # Combine all 2019 employees
    print("\nCombining filtered data...")
    df_2019 = pd.concat(employees_2019, ignore_index=True)
    del employees_2019  # Free memory
    gc.collect()
    
    print(f"Total employees active in 2019: {len(df_2019):,}")
    
    # Get unique employees per company
    print("\nRemoving duplicates...")
    df_unique = df_2019.drop_duplicates(subset=['companyname', 'user_id'])
    print(f"Unique company-employee pairs: {len(df_unique):,}")
    
    # Calculate total employees per company
    print("\nCalculating company sizes...")
    company_totals = df_unique.groupby('companyname')['user_id'].count().reset_index()
    company_totals.columns = ['companyname', 'total_employees_2019']
    
    # Filter companies with at least 10 employees
    company_totals = company_totals[company_totals['total_employees_2019'] >= 10]
    print(f"Companies with 10+ employees: {len(company_totals):,}")
    
    # Keep only employees from these companies
    valid_companies = set(company_totals['companyname'])
    df_unique = df_unique[df_unique['companyname'].isin(valid_companies)]
    
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
    print("\nCreating final dataset...")
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
    
    # Reorder columns
    cols = result.columns.tolist()
    cols.remove('companyname_lower')
    cols.insert(1, 'companyname_lower')
    result = result[cols]
    
    # Save to CSV
    print(f"\nSaving to: {output_path}")
    result.to_csv(output_path, index=False)
    
    # Summary statistics
    print(f"\nProcessing complete in {(time.time() - start_time)/60:.1f} minutes")
    print(f"Final dataset: {len(result):,} companies")
    print(f"Memory usage: {df_unique.memory_usage().sum() / 1024**2:.1f} MB")
    
    # Show sample results
    print("\nComposition Summary (mean % of workforce):")
    print("-"*40)
    
    role_share_cols = [col for col in result.columns if 'share_2019' in col and 'level' not in col]
    for col in sorted(role_share_cols)[:5]:  # Show first 5
        if col in result.columns:
            print(f"{col:<30} {result[col].mean():>6.1f}%")
    
    return result

def estimate_memory_usage(file_path):
    """Estimate memory requirements"""
    print("Estimating memory requirements...")
    
    # Read small sample to estimate
    sample = pd.read_csv(file_path, nrows=10000)
    bytes_per_row = sample.memory_usage(deep=True).sum() / len(sample)
    
    # Get total rows (approximate)
    total_rows = sum(1 for _ in open(file_path)) - 1  # Subtract header
    
    estimated_memory_gb = (bytes_per_row * total_rows) / (1024**3)
    
    print(f"Estimated memory needed: {estimated_memory_gb:.1f} GB")
    print(f"Recommended chunk size: {int(1_000_000 * (8 / estimated_memory_gb)):,} rows")
    
    return int(1_000_000 * (8 / estimated_memory_gb))

def main():
    # Paths
    input_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv")
    output_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/results/raw/composition_precovid_2019.csv")
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return
    
    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Estimate memory and set chunk size
    try:
        # For 32GB system, use 500k rows per chunk (conservative)
        chunksize = 500000
        print(f"Using chunk size: {chunksize:,} rows")
    except:
        chunksize = 500000  # Default fallback
    
    # Run analysis
    try:
        result = process_in_chunks(
            input_path=input_path,
            output_path=output_path,
            chunksize=chunksize
        )
        
        if result is not None:
            print("\nSuccess! Composition variables created.")
            print(f"Output saved to: {output_path}")
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()