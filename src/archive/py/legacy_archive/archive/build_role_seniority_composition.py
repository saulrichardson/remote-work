#!/usr/bin/env python3
"""
Build role × seniority composition variables for HPC analysis
Creates % change in employees by role AND seniority level
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# Configuration
INPUT_FILE = 'data/clean/stacked_linkedin_panel_full.parquet'  # For HPC
OUTPUT_DIR = 'results/raw'
CHUNK_SIZE = 1_000_000

def process_composition():
    """
    Calculate % change in employees by role × seniority combinations
    """
    print(f"Starting composition analysis at {datetime.now()}")
    
    # Initialize storage for results
    all_compositions = []
    
    # Process in chunks
    chunk_num = 0
    for chunk in pd.read_parquet(INPUT_FILE, chunksize=CHUNK_SIZE):
        chunk_num += 1
        print(f"Processing chunk {chunk_num}...")
        
        # Create year-half variable
        chunk['date'] = pd.to_datetime(chunk['date'])
        chunk['year'] = chunk['date'].dt.year
        chunk['half'] = chunk['date'].dt.month.apply(lambda x: 1 if x <= 6 else 2)
        chunk['yh'] = chunk['year'] * 10 + chunk['half']
        
        # Define periods
        chunk['period'] = 'pre'
        chunk.loc[chunk['yh'] >= 20201, 'period'] = 'post'
        
        # Keep only pre/post COVID
        chunk = chunk[chunk['period'].isin(['pre', 'post'])]
        
        # Clean seniority levels
        chunk['seniority_clean'] = chunk['user_seniority'].str.lower()
        chunk['seniority_group'] = 'other'
        chunk.loc[chunk['seniority_clean'].str.contains('entry|junior', na=False), 'seniority_group'] = 'junior'
        chunk.loc[chunk['seniority_clean'].str.contains('senior|lead', na=False), 'seniority_group'] = 'senior'
        chunk.loc[chunk['seniority_clean'].str.contains('manager', na=False), 'seniority_group'] = 'manager'
        chunk.loc[chunk['seniority_clean'].str.contains('director', na=False), 'seniority_group'] = 'director'
        chunk.loc[chunk['seniority_clean'].str.contains('vp|vice', na=False), 'seniority_group'] = 'vp'
        chunk.loc[chunk['seniority_clean'].str.contains('owner|founder|ceo', na=False), 'seniority_group'] = 'exec'
        
        # Extract SOC code
        chunk['soc_code'] = chunk['position_role_soc'].str.replace('-', '')
        
        # Count by company, role, seniority, and period
        counts = chunk.groupby(['companyname', 'soc_code', 'seniority_group', 'period']).size().reset_index(name='n_employees')
        all_compositions.append(counts)
    
    # Combine all chunks
    print("Combining results...")
    full_counts = pd.concat(all_compositions, ignore_index=True)
    
    # Aggregate across chunks
    full_counts = full_counts.groupby(['companyname', 'soc_code', 'seniority_group', 'period'])['n_employees'].sum().reset_index()
    
    # Get top SOCs overall
    top_socs = full_counts.groupby('soc_code')['n_employees'].sum().nlargest(15).index.tolist()
    
    # Calculate % changes
    print("Calculating percentage changes...")
    results = []
    
    for company in full_counts['companyname'].unique():
        company_data = full_counts[full_counts['companyname'] == company]
        
        # 1. Role-only changes (aggregate across seniority)
        role_only = company_data.groupby(['soc_code', 'period'])['n_employees'].sum().reset_index()
        role_pivot = role_only.pivot(index='soc_code', columns='period', values='n_employees').fillna(0)
        
        for soc in top_socs:
            if soc in role_pivot.index:
                pre = role_pivot.loc[soc, 'pre'] if 'pre' in role_pivot.columns else 0
                post = role_pivot.loc[soc, 'post'] if 'post' in role_pivot.columns else 0
                
                if pre > 0:
                    pct_change = 100 * (post - pre) / pre
                elif post > 0:
                    pct_change = 100
                else:
                    pct_change = 0
                    
                results.append({
                    'companyname': company,
                    'variable': f'pct_chg_soc{soc}',
                    'value': pct_change,
                    'type': 'role_only'
                })
        
        # 2. Seniority-only changes (aggregate across roles)
        sen_only = company_data.groupby(['seniority_group', 'period'])['n_employees'].sum().reset_index()
        sen_pivot = sen_only.pivot(index='seniority_group', columns='period', values='n_employees').fillna(0)
        
        for sen in ['junior', 'senior', 'manager', 'director', 'vp', 'exec']:
            if sen in sen_pivot.index:
                pre = sen_pivot.loc[sen, 'pre'] if 'pre' in sen_pivot.columns else 0
                post = sen_pivot.loc[sen, 'post'] if 'post' in sen_pivot.columns else 0
                
                if pre > 0:
                    pct_change = 100 * (post - pre) / pre
                elif post > 0:
                    pct_change = 100
                else:
                    pct_change = 0
                    
                results.append({
                    'companyname': company,
                    'variable': f'pct_chg_{sen}',
                    'value': pct_change,
                    'type': 'seniority_only'
                })
        
        # 3. Role × Seniority interactions (top 5 roles × 3 seniority levels)
        company_pivot = company_data.pivot_table(
            index=['soc_code', 'seniority_group'], 
            columns='period', 
            values='n_employees',
            fill_value=0
        )
        
        # Focus on key combinations
        key_roles = top_socs[:5]  # Top 5 roles
        key_seniorities = ['junior', 'senior', 'manager']
        
        for soc in key_roles:
            for sen in key_seniorities:
                if (soc, sen) in company_pivot.index:
                    pre = company_pivot.loc[(soc, sen), 'pre'] if 'pre' in company_pivot.columns else 0
                    post = company_pivot.loc[(soc, sen), 'post'] if 'post' in company_pivot.columns else 0
                    
                    if pre > 0:
                        pct_change = 100 * (post - pre) / pre
                    elif post > 0:
                        pct_change = 100
                    else:
                        pct_change = 0
                        
                    results.append({
                        'companyname': company,
                        'variable': f'pct_chg_soc{soc}_{sen}',
                        'value': pct_change,
                        'type': 'role_seniority'
                    })
    
    # Convert to wide format
    print("Converting to wide format...")
    results_df = pd.DataFrame(results)
    
    # Pivot to wide
    final_wide = results_df.pivot_table(
        index='companyname',
        columns='variable',
        values='value',
        fill_value=0
    ).reset_index()
    
    # Add lowercase company name
    final_wide['companyname_lower'] = final_wide['companyname'].str.lower()
    
    # Save results
    output_file = os.path.join(OUTPUT_DIR, 'composition_role_seniority_full.dta')
    final_wide.to_stata(output_file, write_index=False)
    print(f"Saved to {output_file}")
    
    # Also save summary statistics
    summary_stats = results_df.groupby(['variable', 'type'])['value'].describe()
    summary_file = os.path.join(OUTPUT_DIR, 'composition_role_seniority_summary.csv')
    summary_stats.to_csv(summary_file)
    print(f"Summary stats saved to {summary_file}")
    
    # Print top variables
    print("\nTop composition changes:")
    top_changes = results_df.groupby('variable')['value'].agg(['mean', 'std', 'count'])
    top_changes = top_changes[top_changes['count'] > 100].sort_values('mean', ascending=False).head(20)
    print(top_changes)
    
    return final_wide

if __name__ == "__main__":
    # For HPC: accept command line args
    if len(sys.argv) > 1:
        INPUT_FILE = sys.argv[1]
    if len(sys.argv) > 2:
        OUTPUT_DIR = sys.argv[2]
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Run analysis
    composition_data = process_composition()
    
    print(f"\nAnalysis complete at {datetime.now()}")
    print(f"Created {len(composition_data.columns)-2} composition variables")
    print(f"Covered {len(composition_data)} firms")