#!/usr/bin/env python3
"""
Build composition change metrics - with correct year-half values
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Create results directory
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def stata_yh(year, half):
    """Convert year and half to Stata's yh format"""
    return (year - 1960) * 2 + (half - 1)

def process_soc_composition():
    """Calculate SOC-based composition changes"""
    
    # Define periods using correct yh values
    pre_covid_yh = stata_yh(2019, 2)  # Should be 119
    post_covid_start = stata_yh(2020, 2)  # Should be 121
    post_covid_end = stata_yh(2021, 1)  # Should be 122
    
    logging.info(f"Using yh values: pre-COVID={pre_covid_yh}, post-COVID={post_covid_start}-{post_covid_end}")
    
    # Read firm-SOC panel
    logging.info("Reading firm-SOC panel...")
    df = pd.read_csv(DATA_DIR / "firm_soc_panel_enriched.csv", 
                     usecols=['companyname', 'soc4', 'yh', 'headcount'])
    
    # Pre-COVID baseline
    pre_df = df[df['yh'] == pre_covid_yh].groupby(['companyname', 'soc4'])['headcount'].sum()
    logging.info(f"Pre-COVID: {len(pre_df)} firm-SOC combinations")
    
    # Post-COVID average
    post_df = df[df['yh'].between(post_covid_start, post_covid_end)].groupby(['companyname', 'soc4', 'yh'])['headcount'].sum()
    post_df = post_df.groupby(['companyname', 'soc4']).mean()  # Average across periods
    logging.info(f"Post-COVID: {len(post_df)} firm-SOC combinations")
    
    # Calculate changes
    changes = []
    all_keys = set(pre_df.index) | set(post_df.index)
    
    for company, soc in all_keys:
        pre_count = pre_df.get((company, soc), 0)
        post_count = post_df.get((company, soc), 0)
        
        if pre_count > 0:
            pct_change = 100 * (post_count - pre_count) / pre_count
        elif post_count > 0:
            pct_change = 100  # New role
        else:
            continue
            
        changes.append({
            'companyname': company,
            'soc4': soc,
            'pre_count': pre_count,
            'post_count': post_count,
            'pct_change': pct_change
        })
    
    df_changes = pd.DataFrame(changes)
    
    # Get top SOCs by employment
    top_socs = df_changes.groupby('soc4')['pre_count'].sum().nlargest(15).index
    
    # Create wide format
    wide_df = df_changes[df_changes['soc4'].isin(top_socs)].pivot(
        index='companyname',
        columns='soc4', 
        values='pct_change'
    ).fillna(0)
    
    # Rename columns
    wide_df.columns = [f'pct_chg_soc{col}' for col in wide_df.columns]
    wide_df.reset_index(inplace=True)
    
    # Save
    wide_df.to_csv(RESULTS_DIR / "firm_soc_composition_wide.csv", index=False)
    logging.info(f"Saved SOC composition for {len(wide_df)} firms, {len(wide_df.columns)-1} SOCs")
    
    # Create summary stats
    summary = pd.DataFrame({
        'soc4': top_socs,
        'avg_pct_change': [df_changes[df_changes['soc4']==soc]['pct_change'].mean() for soc in top_socs],
        'firms_with_soc': [df_changes[df_changes['soc4']==soc].shape[0] for soc in top_socs]
    })
    summary.to_csv(RESULTS_DIR / "soc_composition_summary.csv", index=False)
    
    return wide_df

def process_seniority_composition():
    """Calculate seniority-based composition changes"""
    
    logging.info("Processing seniority composition...")
    
    # Read firm panel
    df = pd.read_stata(DATA_DIR / "firm_panel.dta", 
                       columns=['companyname', 'yh', 'seniority_levels', 'total_employees'])
    
    # Define periods
    pre_yh = stata_yh(2019, 2)
    post_start = stata_yh(2020, 2)
    post_end = stata_yh(2021, 1)
    
    # Pre-COVID
    pre_df = df[df['yh'] == pre_yh][['companyname', 'seniority_levels', 'total_employees']]
    pre_df.columns = ['companyname', 'sen_pre', 'emp_pre']
    
    # Post-COVID average
    post_df = df[df['yh'].between(post_start, post_end)].groupby('companyname').agg({
        'seniority_levels': 'mean',
        'total_employees': 'mean'
    }).reset_index()
    post_df.columns = ['companyname', 'sen_post', 'emp_post']
    
    # Merge and calculate changes
    sen_df = pre_df.merge(post_df, on='companyname', how='outer')
    
    # Calculate metrics
    sen_df['sen_change'] = sen_df['sen_post'] - sen_df['sen_pre']
    sen_df['sen_pct_change'] = 100 * sen_df['sen_change'] / sen_df['sen_pre']
    sen_df['emp_growth'] = 100 * (sen_df['emp_post'] - sen_df['emp_pre']) / sen_df['emp_pre']
    
    # Handle infinities
    sen_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # Save
    sen_df.to_csv(RESULTS_DIR / "firm_seniority_composition.csv", index=False)
    logging.info(f"Saved seniority data for {len(sen_df)} firms")
    
    return sen_df

def create_test_regressions():
    """Create simple test regressions to verify the approach"""
    
    logging.info("Creating test regression code...")
    
    test_code = '''
* Test composition regressions on small sample
clear all
set more off

* Load SOC composition
import delimited "results/raw/firm_soc_composition_wide.csv", clear
save "results/raw/soc_comp_temp.dta", replace

* Load firm panel and merge
use "data/clean/firm_panel.dta", clear
keep if yh >= 119  // 2019 onwards
merge m:1 companyname using "results/raw/soc_comp_temp.dta", nogen keep(match)

* Simple test: Does composition change predict growth?
reg growth_rate_we pct_chg_soc1511 pct_chg_soc1311 pct_chg_soc1320 startup if yh > 120

* Display results
di "Test regression results:"
di "N = " e(N)
di "R2 = " e(r2)
'''
    
    with open(ROOT / "spec" / "test_composition_regression.do", 'w') as f:
        f.write(test_code)
    
    logging.info("Created test regression script")

if __name__ == "__main__":
    # Process compositions
    soc_comp = process_soc_composition()
    sen_comp = process_seniority_composition()
    
    # Create test code
    create_test_regressions()
    
    # Display summary
    print("\nComposition analysis complete!")
    print(f"SOC composition: {len(soc_comp)} firms")
    print(f"Seniority composition: {len(sen_comp)} firms")
    print("\nTop SOCs included:", [col.replace('pct_chg_soc', '') for col in soc_comp.columns if 'pct_chg' in col])