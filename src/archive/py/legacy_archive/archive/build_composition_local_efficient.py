#!/usr/bin/env python3
"""
Build role × seniority composition variables locally with efficient memory management
Processes LinkedIn data in chunks to work on local machine
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
import gc

# Configuration
INPUT_FILE = 'data/clean/Scoop_Positions_Firm_Collapse2.csv'  # Scoop LinkedIn data
OUTPUT_DIR = 'results/raw'
CHUNK_SIZE = 100_000  # Process 100k rows at a time

# Define top SOCs and seniority groups upfront to limit variables
TOP_SOCS = ['151132', '132011', '119111', '131111', '412011', 
            '172171', '434051', '111021', '113111', '131071']
SENIORITY_GROUPS = ['junior', 'senior', 'manager', 'director']

def process_chunk(chunk):
    """
    Process a single chunk to extract counts
    """
    # Create date variables
    chunk['date'] = pd.to_datetime(chunk['date'])
    chunk['yh'] = pd.Period(chunk['date'].dt.to_period('Q').astype(str).str[:4] + '-' + 
                            np.where(chunk['date'].dt.quarter <= 2, 'H1', 'H2')).ordinal
    
    # Define periods based on COVID (2020H1 = 4040 in Stata encoding)
    chunk['period'] = 'pre'
    chunk.loc[chunk['yh'] >= 4040, 'period'] = 'post'
    
    # Keep only pre/post COVID
    chunk = chunk[chunk['period'].isin(['pre', 'post'])]
    
    # Clean seniority - simplified mapping
    chunk['seniority_clean'] = chunk['user_seniority'].str.lower().fillna('other')
    chunk['seniority_group'] = 'other'
    
    # Map to groups
    junior_keywords = ['entry', 'junior', 'associate', 'analyst']
    senior_keywords = ['senior', 'lead', 'principal']
    manager_keywords = ['manager', 'head']
    director_keywords = ['director', 'vp', 'vice president']
    
    for keyword in junior_keywords:
        chunk.loc[chunk['seniority_clean'].str.contains(keyword, na=False), 'seniority_group'] = 'junior'
    for keyword in senior_keywords:
        chunk.loc[chunk['seniority_clean'].str.contains(keyword, na=False), 'seniority_group'] = 'senior'
    for keyword in manager_keywords:
        chunk.loc[chunk['seniority_clean'].str.contains(keyword, na=False), 'seniority_group'] = 'manager'
    for keyword in director_keywords:
        chunk.loc[chunk['seniority_clean'].str.contains(keyword, na=False), 'seniority_group'] = 'director'
    
    # Handle missing columns gracefully
    if 'position_role_soc' in chunk.columns:
        chunk['soc_code'] = chunk['position_role_soc'].str.replace('-', '').str.strip()
    else:
        # For firm-level data, we'll need to process differently
        return pd.DataFrame()  # Return empty for now
    
    # Filter to top SOCs only to reduce memory
    chunk = chunk[chunk['soc_code'].isin(TOP_SOCS) | chunk['seniority_group'].isin(SENIORITY_GROUPS)]
    
    # Count by company, role, seniority, and period
    counts = chunk.groupby(['companyname', 'soc_code', 'seniority_group', 'period']).size().reset_index(name='n')
    
    return counts

def calculate_pct_changes(counts_df):
    """
    Calculate percentage changes from counts
    """
    results = []
    
    for company in counts_df['companyname'].unique():
        company_data = counts_df[counts_df['companyname'] == company]
        result_row = {'companyname': company}
        
        # 1. Role-only changes
        role_counts = company_data.groupby(['soc_code', 'period'])['n'].sum().unstack(fill_value=0)
        for soc in TOP_SOCS:
            if soc in role_counts.index:
                pre = role_counts.loc[soc, 'pre'] if 'pre' in role_counts.columns else 0
                post = role_counts.loc[soc, 'post'] if 'post' in role_counts.columns else 0
                
                if pre > 0:
                    pct = 100 * (post - pre) / pre
                elif post > 0:
                    pct = 100
                else:
                    pct = 0
                    
                result_row[f'pct_chg_soc{soc}'] = pct
        
        # 2. Seniority-only changes  
        sen_counts = company_data.groupby(['seniority_group', 'period'])['n'].sum().unstack(fill_value=0)
        for sen in SENIORITY_GROUPS:
            if sen in sen_counts.index:
                pre = sen_counts.loc[sen, 'pre'] if 'pre' in sen_counts.columns else 0
                post = sen_counts.loc[sen, 'post'] if 'post' in sen_counts.columns else 0
                
                if pre > 0:
                    pct = 100 * (post - pre) / pre
                elif post > 0:
                    pct = 100
                else:
                    pct = 0
                    
                result_row[f'pct_chg_{sen}'] = pct
        
        # 3. Key role × seniority combinations (limit to reduce memory)
        key_combos = [
            ('132011', 'senior'),  # Senior finance
            ('132011', 'junior'),  # Junior finance
            ('151132', 'senior'),  # Senior software
            ('151132', 'junior'),  # Junior software
            ('119111', 'manager'), # Management managers
        ]
        
        combo_data = company_data.pivot_table(
            index=['soc_code', 'seniority_group'],
            columns='period',
            values='n',
            fill_value=0
        )
        
        for soc, sen in key_combos:
            if (soc, sen) in combo_data.index:
                pre = combo_data.loc[(soc, sen), 'pre'] if 'pre' in combo_data.columns else 0
                post = combo_data.loc[(soc, sen), 'post'] if 'post' in combo_data.columns else 0
                
                if pre > 0:
                    pct = 100 * (post - pre) / pre
                elif post > 0:
                    pct = 100
                else:
                    pct = 0
                    
                result_row[f'pct_chg_soc{soc}_{sen}'] = pct
        
        results.append(result_row)
    
    return pd.DataFrame(results)

def main():
    """
    Main processing function
    """
    print(f"Starting composition analysis at {datetime.now()}")
    print(f"Processing file: {INPUT_FILE}")
    
    # Check if we're using sample or full data
    if '1m' in INPUT_FILE:
        print("Using 1M sample - results will be illustrative")
    
    # Initialize storage
    all_counts = []
    
    # Process file in chunks
    chunk_num = 0
    try:
        for chunk in pd.read_csv(INPUT_FILE, chunksize=CHUNK_SIZE):
            chunk_num += 1
            if chunk_num % 10 == 0:
                print(f"Processing chunk {chunk_num}...")
            
            # Process chunk
            chunk_counts = process_chunk(chunk)
            all_counts.append(chunk_counts)
            
            # Free memory
            del chunk
            gc.collect()
    
    except Exception as e:
        print(f"Error processing chunks: {e}")
        return None
    
    # Combine all chunks
    print("\nCombining chunk results...")
    combined_counts = pd.concat(all_counts, ignore_index=True)
    del all_counts
    gc.collect()
    
    # Aggregate counts across chunks
    print("Aggregating counts...")
    final_counts = combined_counts.groupby(['companyname', 'soc_code', 'seniority_group', 'period'])['n'].sum().reset_index()
    del combined_counts
    gc.collect()
    
    # Calculate percentage changes
    print("Calculating percentage changes...")
    results_df = calculate_pct_changes(final_counts)
    
    # Add lowercase company name
    results_df['companyname_lower'] = results_df['companyname'].str.lower()
    
    # Fill missing values with 0
    numeric_cols = [col for col in results_df.columns if col.startswith('pct_chg_')]
    results_df[numeric_cols] = results_df[numeric_cols].fillna(0)
    
    # Save results
    output_file = os.path.join(OUTPUT_DIR, 'composition_role_seniority_sample.dta')
    results_df.to_stata(output_file, write_index=False)
    print(f"\nSaved to {output_file}")
    
    # Print summary statistics
    print("\nSummary of composition changes:")
    print("\nRole changes:")
    for col in [c for c in numeric_cols if c.startswith('pct_chg_soc') and '_' not in c[12:]]:
        print(f"{col}: mean={results_df[col].mean():.1f}%, non-zero={(results_df[col] != 0).sum()}")
    
    print("\nSeniority changes:")
    for col in [c for c in numeric_cols if c.startswith('pct_chg_') and not c.startswith('pct_chg_soc')]:
        print(f"{col}: mean={results_df[col].mean():.1f}%, non-zero={(results_df[col] != 0).sum()}")
    
    print("\nRole × Seniority changes:")
    for col in [c for c in numeric_cols if '_senior' in col or '_junior' in col or '_manager' in col]:
        print(f"{col}: mean={results_df[col].mean():.1f}%, non-zero={(results_df[col] != 0).sum()}")
    
    print(f"\nTotal firms: {len(results_df)}")
    print(f"Total variables created: {len(numeric_cols)}")
    
    return results_df

if __name__ == "__main__":
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Run analysis
    results = main()
    
    if results is not None:
        print(f"\nAnalysis complete at {datetime.now()}")
    else:
        print("\nAnalysis failed - check error messages above")