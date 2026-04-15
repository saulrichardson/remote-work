#!/usr/bin/env python3
"""
Build composition change metrics from LinkedIn panel data.
Memory-efficient approach using chunked processing.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

# Setup
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def process_linkedin_chunks(chunk_size=1_000_000):
    """Process LinkedIn panel in chunks to calculate composition changes."""
    
    # Define time periods
    pre_covid = [4022, 4023]  # 2019 H1, H2
    post_covid = [4032, 4033]  # 2020 H2, 2021 H1
    
    # Initialize aggregators
    pre_totals = {}
    post_totals = {}
    
    logging.info("Processing LinkedIn panel in chunks...")
    
    # Read and process in chunks
    for chunk in pd.read_csv(DATA_DIR / "linkedin_panel_pandas.csv", chunksize=chunk_size):
        # Pre-COVID aggregation
        pre_chunk = chunk[chunk['yh'].isin(pre_covid)]
        pre_agg = pre_chunk.groupby(['companyname', 'soc6'])['headcount'].sum()
        
        # Post-COVID aggregation
        post_chunk = chunk[chunk['yh'].isin(post_covid)]
        post_agg = post_chunk.groupby(['companyname', 'soc6'])['headcount'].mean()
        
        # Update totals
        for (company, soc), count in pre_agg.items():
            key = (company, soc)
            pre_totals[key] = pre_totals.get(key, 0) + count
            
        for (company, soc), count in post_agg.items():
            key = (company, soc)
            if key not in post_totals:
                post_totals[key] = []
            post_totals[key].append(count)
    
    logging.info(f"Processed {len(pre_totals)} firm-SOC combinations")
    
    # Calculate average post-COVID counts
    for key in post_totals:
        post_totals[key] = np.mean(post_totals[key])
    
    # Calculate percentage changes
    composition_changes = []
    
    for (company, soc) in set(list(pre_totals.keys()) + list(post_totals.keys())):
        pre_count = pre_totals.get((company, soc), 0)
        post_count = post_totals.get((company, soc), 0)
        
        if pre_count > 0:
            pct_change = 100 * (post_count - pre_count) / pre_count
        elif post_count > 0:
            pct_change = 100  # New role
        else:
            pct_change = 0
            
        # Extract SOC4 code
        soc4 = str(soc)[:4] if len(str(soc)) >= 4 else str(soc)
        
        composition_changes.append({
            'companyname': company,
            'soc6': soc,
            'soc4': soc4,
            'pre_count': pre_count,
            'post_count': post_count,
            'pct_change': pct_change
        })
    
    df_changes = pd.DataFrame(composition_changes)
    
    # Save detailed results
    df_changes.to_csv(RESULTS_DIR / "soc_composition_changes_detailed.csv", index=False)
    
    # Create SOC4 aggregated version
    soc4_agg = df_changes.groupby(['companyname', 'soc4']).agg({
        'pre_count': 'sum',
        'post_count': 'sum'
    }).reset_index()
    
    soc4_agg['pct_change_soc4'] = 100 * (soc4_agg['post_count'] - soc4_agg['pre_count']) / soc4_agg['pre_count']
    soc4_agg.loc[soc4_agg['pre_count'] == 0, 'pct_change_soc4'] = 100
    
    # Identify top 20 SOC4 codes by total employment
    top_socs = soc4_agg.groupby('soc4')['pre_count'].sum().nlargest(20).index.tolist()
    
    # Create wide format for top SOCs
    wide_changes = soc4_agg[soc4_agg['soc4'].isin(top_socs)].pivot(
        index='companyname',
        columns='soc4',
        values='pct_change_soc4'
    ).fillna(0)
    
    wide_changes.columns = [f'pct_chg_soc_{col}' for col in wide_changes.columns]
    wide_changes.reset_index(inplace=True)
    
    # Save wide format
    wide_changes.to_csv(RESULTS_DIR / "firm_soc_composition_wide.csv", index=False)
    logging.info(f"Saved composition changes for {len(wide_changes)} firms")
    
    return wide_changes

def calculate_seniority_metrics():
    """Calculate seniority-based metrics from firm panel."""
    
    logging.info("Calculating seniority metrics...")
    
    # Read firm panel
    df = pd.read_stata(DATA_DIR / "firm_panel.dta")
    
    # Pre-COVID baseline
    pre_df = df[df['yh'] == 4023][['companyname', 'seniority_levels', 'total_employees']]
    pre_df.columns = ['companyname', 'sen_levels_pre', 'emp_pre']
    
    # Post-COVID average
    post_df = df[df['yh'].between(4032, 4033)].groupby('companyname').agg({
        'seniority_levels': 'mean',
        'total_employees': 'mean'
    }).reset_index()
    post_df.columns = ['companyname', 'sen_levels_post', 'emp_post']
    
    # Merge and calculate changes
    sen_changes = pre_df.merge(post_df, on='companyname', how='outer')
    
    # Calculate metrics
    sen_changes['sen_concentration_chg'] = (
        100 * (sen_changes['sen_levels_post'] - sen_changes['sen_levels_pre']) 
        / sen_changes['sen_levels_pre']
    )
    sen_changes['emp_growth'] = (
        100 * (sen_changes['emp_post'] - sen_changes['emp_pre']) 
        / sen_changes['emp_pre']
    )
    
    # Save
    sen_changes.to_csv(RESULTS_DIR / "firm_seniority_changes.csv", index=False)
    logging.info(f"Saved seniority metrics for {len(sen_changes)} firms")
    
    return sen_changes

def create_analysis_datasets():
    """Merge composition changes with main datasets."""
    
    logging.info("Creating analysis datasets...")
    
    # Load composition changes
    soc_comp = pd.read_csv(RESULTS_DIR / "firm_soc_composition_wide.csv")
    sen_comp = pd.read_csv(RESULTS_DIR / "firm_seniority_changes.csv")
    
    # Merge both
    comp_full = soc_comp.merge(sen_comp[['companyname', 'sen_concentration_chg', 'emp_growth']], 
                               on='companyname', how='outer')
    
    # Save combined dataset
    comp_full.to_stata(DATA_DIR / "firm_composition_changes.dta", write_index=False)
    comp_full.to_csv(DATA_DIR / "firm_composition_changes.csv", index=False)
    
    logging.info("Created combined composition dataset")
    
    # Create summary statistics
    summary = pd.DataFrame({
        'metric': ['firms_with_soc_changes', 'firms_with_sen_changes', 
                   'avg_soc_changes', 'avg_sen_concentration_chg'],
        'value': [
            soc_comp.shape[0],
            sen_comp.dropna(subset=['sen_concentration_chg']).shape[0],
            soc_comp.iloc[:, 1:].mean().mean(),
            sen_comp['sen_concentration_chg'].mean()
        ]
    })
    
    summary.to_csv(RESULTS_DIR / "composition_summary_stats.csv", index=False)
    logging.info("Summary statistics saved")

if __name__ == "__main__":
    # Process LinkedIn data for SOC changes
    soc_changes = process_linkedin_chunks()
    
    # Calculate seniority metrics
    sen_changes = calculate_seniority_metrics()
    
    # Create merged datasets
    create_analysis_datasets()
    
    logging.info("Composition analysis complete!")