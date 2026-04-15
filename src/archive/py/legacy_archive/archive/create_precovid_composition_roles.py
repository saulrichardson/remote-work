#!/usr/bin/env python3
"""
Create Pre-COVID (2019) Composition Variables using role_k7
Tests on partial data first, then can run on full dataset
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
import time

def create_composition_variables(sample_size=None):
    """
    Create pre-COVID composition variables from LinkedIn data
    
    Args:
        sample_size: Number of rows to read (None for full data)
    """
    # Start timer
    start_time = time.time()
    
    # Connect to DuckDB with more memory
    con = duckdb.connect(':memory:')
    con.execute("SET memory_limit='4GB'")
    con.execute("SET threads TO 4")
    
    print("Creating Pre-COVID Composition Variables")
    print("="*60)
    
    # Path to LinkedIn data
    linkedin_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv")
    
    # Read data
    if sample_size:
        print(f"Reading first {sample_size:,} rows for testing...")
        read_query = f"""
            SELECT companyname, user_id, role_k7, seniority, start_date, end_date
            FROM read_csv_auto('{linkedin_path}', sample_size={sample_size}, strict_mode=false)
            WHERE companyname IS NOT NULL
              AND role_k7 IS NOT NULL
              AND seniority IS NOT NULL
        """
    else:
        print("Reading full dataset...")
        read_query = f"""
            SELECT companyname, user_id, role_k7, seniority, start_date, end_date
            FROM read_csv_auto('{linkedin_path}', strict_mode=false)
            WHERE companyname IS NOT NULL
              AND role_k7 IS NOT NULL
              AND seniority IS NOT NULL
        """
    
    # Create main query
    query = f"""
    WITH 
    -- Step 1: Load and filter data
    raw_data AS ({read_query}),
    
    -- Step 2: Get employees active in 2019
    employees_2019 AS (
        SELECT DISTINCT
            companyname,
            user_id,
            role_k7,
            seniority
        FROM raw_data
        WHERE 
            -- Was working during 2019
            (end_date >= '2019-01-01' OR end_date IS NULL)
            AND (start_date IS NULL OR start_date <= '2019-12-31')
    ),
    
    -- Step 3: Count employees by company
    company_counts AS (
        SELECT 
            companyname,
            COUNT(DISTINCT user_id) as total_employees_2019
        FROM employees_2019
        GROUP BY companyname
    ),
    
    -- Step 4: Calculate composition percentages
    composition AS (
        SELECT 
            e.companyname,
            cc.total_employees_2019,
            
            -- Role composition (% of workforce)
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Engineer' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as engineer_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Sales' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as sales_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Finance' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as finance_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Marketing' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as marketing_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Admin' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as admin_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Operations' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as operations_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Scientist' THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as scientist_share_2019,
            
            -- Seniority composition (% of workforce)
            COUNT(DISTINCT CASE WHEN e.seniority = 1 THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as level1_share_2019,
            COUNT(DISTINCT CASE WHEN e.seniority = 2 THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as level2_share_2019,
            COUNT(DISTINCT CASE WHEN e.seniority = 3 THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as level3_share_2019,
            COUNT(DISTINCT CASE WHEN e.seniority = 4 THEN e.user_id END) * 100.0 
                / cc.total_employees_2019 as level4_share_2019,
                
            -- Key role × seniority interactions
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Engineer' AND e.seniority IN (1,2) 
                THEN e.user_id END) * 100.0 / cc.total_employees_2019 as junior_engineer_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Engineer' AND e.seniority IN (3,4) 
                THEN e.user_id END) * 100.0 / cc.total_employees_2019 as senior_engineer_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Sales' AND e.seniority IN (1,2) 
                THEN e.user_id END) * 100.0 / cc.total_employees_2019 as junior_sales_share_2019,
            COUNT(DISTINCT CASE WHEN e.role_k7 = 'Finance' AND e.seniority IN (3,4) 
                THEN e.user_id END) * 100.0 / cc.total_employees_2019 as senior_finance_share_2019
                
        FROM employees_2019 e
        JOIN company_counts cc ON e.companyname = cc.companyname
        GROUP BY e.companyname, cc.total_employees_2019
    )
    
    SELECT * FROM composition
    WHERE total_employees_2019 >= 10  -- Minimum firm size
    ORDER BY companyname
    """
    
    # Execute query
    print("\nCalculating composition variables...")
    result = con.execute(query).fetchdf()
    
    # Print summary statistics
    print(f"\nProcessing complete in {time.time() - start_time:.1f} seconds")
    print(f"Number of companies: {len(result):,}")
    print(f"Average employees per company: {result['total_employees_2019'].mean():.1f}")
    
    # Show distribution of key variables
    print("\nComposition Summary (mean % of workforce):")
    print("-"*40)
    for col in ['engineer_share_2019', 'sales_share_2019', 'finance_share_2019', 
                'level1_share_2019', 'level2_share_2019', 'level3_share_2019', 'level4_share_2019']:
        if col in result.columns:
            print(f"{col:<25} {result[col].mean():>6.1f}%")
    
    # Show sample of results
    print("\nSample Results (first 5 companies):")
    print("-"*60)
    display_cols = ['companyname', 'total_employees_2019', 'engineer_share_2019', 
                    'sales_share_2019', 'level1_share_2019']
    print(result[display_cols].head())
    
    # Check for potential issues
    print("\nData Quality Checks:")
    print("-"*40)
    
    # Check if percentages sum to ~100
    role_sum = result[['engineer_share_2019', 'sales_share_2019', 'finance_share_2019', 
                      'marketing_share_2019', 'admin_share_2019', 'operations_share_2019', 
                      'scientist_share_2019']].sum(axis=1)
    print(f"Role percentages sum - Mean: {role_sum.mean():.1f}%, Std: {role_sum.std():.1f}%")
    
    seniority_sum = result[['level1_share_2019', 'level2_share_2019', 
                           'level3_share_2019', 'level4_share_2019']].sum(axis=1)
    print(f"Seniority percentages sum - Mean: {seniority_sum.mean():.1f}%, Std: {seniority_sum.std():.1f}%")
    
    # Save to CSV
    output_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/results/raw/composition_precovid_2019.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")
    
    con.close()
    return result

if __name__ == "__main__":
    # Test with 500k rows first
    print("Testing with 500,000 rows...")
    df_test = create_composition_variables(sample_size=500000)
    
    print("\n" + "="*60)
    print("Test successful! To run on full data, use:")
    print("  df_full = create_composition_variables(sample_size=None)")
    print("="*60)