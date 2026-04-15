#!/usr/bin/env python3
"""
Create Role × Seniority Composition Variables from Raw LinkedIn Data

This script:
1. Loads raw LinkedIn positions data (Scoop_workers_positions.csv)
2. Categorizes employees by SOC code and seniority level
3. Calculates percentage changes in composition by firm
4. Outputs composition variables for firm-level analysis
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
import argparse

def main(sample_size=None):
    # Connect to DuckDB with more memory
    con = duckdb.connect(':memory:')
    con.execute("SET memory_limit='8GB'")
    con.execute("SET threads TO 8")
    
    # Define top 15 SOCs by employment
    top_socs = [
        '151132',  # Software Developers, Applications
        '132011',  # Accountants and Auditors  
        '119111',  # Medical and Health Services Managers
        '131111',  # Management Analysts
        '412031',  # Retail Salespersons
        '111021',  # General and Operations Managers
        '131071',  # Human Resources Specialists
        '131161',  # Market Research Analysts
        '151134',  # Web Developers
        '131051',  # Cost Estimators
        '113021',  # Computer and Information Systems Managers
        '131041',  # Compliance Officers
        '131199',  # Business Operations Specialists
        '119021',  # Construction Managers
        '119041',  # Architectural and Engineering Managers
    ]
    
    print("Loading LinkedIn positions data...")
    
    # Path to raw LinkedIn data
    linkedin_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv")
    
    # Load data with sample if specified
    if sample_size:
        read_cmd = f"SELECT * FROM read_csv_auto('{linkedin_path}', sample_size={sample_size})"
    else:
        read_cmd = f"SELECT * FROM read_csv_auto('{linkedin_path}')"
    
    # Create the main query
    query = f"""
    WITH
    -- Step 1: Load and clean data
    raw_data AS (
        SELECT 
            user_id,
            LOWER(TRIM(company_priname)) as companyname,
            CAST(start_date AS DATE) as start_date,
            CAST(end_date AS DATE) as end_date,
            REPLACE(CAST(occ_cd AS VARCHAR), '-', '') as soc_code,
            LOWER(TRIM(seniority)) as seniority_raw
        FROM ({read_cmd})
        WHERE company_priname IS NOT NULL
          AND company_priname != ''
          AND occ_cd IS NOT NULL
          AND start_date IS NOT NULL
    ),
    
    -- Step 2: Expand to monthly snapshots
    monthly_data AS (
        SELECT 
            rd.*,
            generate_series(
                DATE_TRUNC('month', rd.start_date),
                COALESCE(DATE_TRUNC('month', rd.end_date), '2023-12-01'),
                INTERVAL 1 MONTH
            ) as snapshot_date
        FROM raw_data rd
    ),
    
    -- Step 3: Categorize data
    categorized AS (
        SELECT
            companyname,
            user_id,
            snapshot_date as date,
            soc_code,
            CASE
                WHEN seniority_raw LIKE '%entry%' OR 
                     seniority_raw LIKE '%junior%' OR
                     seniority_raw LIKE '%associate%' AND 
                     seniority_raw NOT LIKE '%senior associate%' THEN 'junior'
                WHEN seniority_raw LIKE '%senior%' OR 
                     seniority_raw LIKE '%lead%' OR
                     seniority_raw LIKE '%principal%' THEN 'senior'
                WHEN seniority_raw LIKE '%manager%' AND 
                     seniority_raw NOT LIKE '%senior manager%' THEN 'manager'
                WHEN seniority_raw LIKE '%director%' OR 
                     seniority_raw LIKE '%vp%' OR 
                     seniority_raw LIKE '%vice president%' THEN 'director'
                WHEN seniority_raw LIKE '%chief%' OR 
                     seniority_raw LIKE '%c-suite%' OR
                     seniority_raw LIKE '%owner%' OR
                     seniority_raw LIKE '%founder%' OR
                     seniority_raw LIKE '%president%' AND 
                     seniority_raw NOT LIKE '%vice president%' THEN 'exec'
                ELSE 'other'
            END as seniority_group,
            CASE
                WHEN date >= '2018-01-01' AND date < '2020-01-01' THEN 'pre'
                WHEN date >= '2020-01-01' AND date <= '2021-12-31' THEN 'post'
                ELSE 'exclude'
            END as period
        FROM monthly_data
    ),

    -- Step 4: Get average headcount by firm/role/seniority/period
    period_counts AS (
        SELECT
            companyname,
            LEFT(soc_code, 6) as soc_code,  -- Use 6-digit SOC
            seniority_group,
            period,
            COUNT(DISTINCT user_id || '_' || date) / COUNT(DISTINCT date) as avg_employees
        FROM categorized
        WHERE period IN ('pre', 'post')
          AND seniority_group != 'other'
          AND LENGTH(soc_code) >= 6
        GROUP BY companyname, LEFT(soc_code, 6), seniority_group, period
    ),

    -- Step 5: Get total employees by firm and period
    firm_totals AS (
        SELECT
            companyname,
            period,
            SUM(avg_employees) as total_employees
        FROM period_counts
        GROUP BY companyname, period
        HAVING total_employees >= 10  -- Filter tiny firms
    ),

    -- Step 6: Calculate shares and changes
    changes AS (
        SELECT
            pc.companyname,
            pc.soc_code,
            pc.seniority_group,
            MAX(CASE WHEN pc.period = 'pre' THEN pc.avg_employees / ft.total_employees ELSE 0 END) as share_pre,
            MAX(CASE WHEN pc.period = 'post' THEN pc.avg_employees / ft.total_employees ELSE 0 END) as share_post
        FROM period_counts pc
        JOIN firm_totals ft
          ON pc.companyname = ft.companyname
          AND pc.period = ft.period
        GROUP BY pc.companyname, pc.soc_code, pc.seniority_group
    ),

    -- Step 7: Calculate percentage point changes
    final_changes AS (
        SELECT
            companyname,
            soc_code,
            seniority_group,
            (share_post - share_pre) * 100 as ppt_change
        FROM changes
        WHERE share_pre > 0 OR share_post > 0  -- Exclude if zero in both periods
    )

    -- Create final output
    SELECT 
        companyname,
        -- Role variables (percentage point changes)
    """
    
    # Add role variables
    for soc in top_socs:
        query += f"""
        SUM(CASE WHEN soc_code = '{soc}' THEN ppt_change ELSE 0 END) as pct_chg_soc{soc},"""
    
    # Add seniority variables
    for seniority in ['junior', 'senior', 'manager', 'director', 'exec']:
        query += f"""
        SUM(CASE WHEN seniority_group = '{seniority}' THEN ppt_change ELSE 0 END) as pct_chg_{seniority},"""
    
    # Add key role × seniority interactions
    key_interactions = [
        ('151132', 'junior'),   # Junior software developers
        ('151132', 'senior'),   # Senior software developers
        ('132011', 'junior'),   # Junior accountants
        ('132011', 'senior'),   # Senior accountants
        ('119111', 'manager'),  # Manager-level health services managers
        ('131111', 'senior'),   # Senior management analysts
        ('111021', 'director'), # Director-level general managers
        ('113021', 'director'), # Director-level IT managers
        ('131071', 'manager'),  # Manager-level HR specialists
        ('131161', 'senior'),   # Senior market research analysts
    ]
    
    for soc, seniority in key_interactions:
        query += f"""
        SUM(CASE WHEN soc_code = '{soc}' AND seniority_group = '{seniority}' THEN ppt_change ELSE 0 END) as pct_chg_soc{soc}_{seniority},"""
    
    # Remove trailing comma and complete query
    query = query.rstrip(',') + """
    FROM final_changes
    GROUP BY companyname
    HAVING COUNT(*) > 0  -- Ensure firm has some data
    ORDER BY companyname
    """
    
    print("Running composition analysis...")
    print("This may take several minutes for the full dataset...")
    
    # Execute query
    result = con.execute(query).fetchdf()
    
    # Save to CSV
    output_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/results/raw/composition_role_seniority_full.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"Saved composition variables to {output_path}")
    
    # Display summary
    print("\nSummary of composition variables:")
    print(f"Number of firms: {len(result)}")
    print(f"Number of variables: {len(result.columns) - 1}")
    
    # Show sample of results
    print("\nSample of results (first 5 firms, first 5 variables):")
    print(result.iloc[:5, :6])
    
    # Show distribution of changes
    print("\nDistribution of composition changes:")
    for col in ['pct_chg_soc151132', 'pct_chg_junior', 'pct_chg_senior']:
        if col in result.columns:
            print(f"\n{col}:")
            print(result[col].describe().round(2))
    
    con.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create composition variables from LinkedIn data')
    parser.add_argument('--sample', type=int, help='Process only first N rows (for testing)')
    args = parser.parse_args()
    
    main(sample_size=args.sample)