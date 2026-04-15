#!/usr/bin/env python3
"""
Create Role × Seniority Composition Variables from LinkedIn Panel Data

This script:
1. Loads LinkedIn panel data
2. Categorizes employees by SOC code and seniority level
3. Calculates percentage changes in composition by firm
4. Outputs composition variables for firm-level analysis
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

def main():
    # Connect to DuckDB
    con = duckdb.connect(':memory:')
    
    # Define top 15 SOCs by employment (these should be customized based on your data)
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
    
    # Create the main query
    query = f"""
    WITH
    -- Step 1: Clean and categorize data
    cleaned_data AS (
        SELECT
            companyname,
            user_id,
            date,
            REPLACE(position_role_soc, '-', '') as soc_code,
            CASE
                WHEN LOWER(user_seniority) LIKE '%entry%' OR 
                     LOWER(user_seniority) LIKE '%junior%' OR
                     LOWER(user_seniority) LIKE '%associate%' AND 
                     NOT LOWER(user_seniority) LIKE '%senior associate%' THEN 'junior'
                WHEN LOWER(user_seniority) LIKE '%senior%' OR 
                     LOWER(user_seniority) LIKE '%lead%' OR
                     LOWER(user_seniority) LIKE '%principal%' THEN 'senior'
                WHEN LOWER(user_seniority) LIKE '%manager%' AND 
                     NOT LOWER(user_seniority) LIKE '%senior manager%' THEN 'manager'
                WHEN LOWER(user_seniority) LIKE '%director%' OR 
                     LOWER(user_seniority) LIKE '%vp%' OR 
                     LOWER(user_seniority) LIKE '%vice president%' THEN 'director'
                WHEN LOWER(user_seniority) LIKE '%chief%' OR 
                     LOWER(user_seniority) LIKE '%owner%' OR
                     LOWER(user_seniority) LIKE '%founder%' OR
                     LOWER(user_seniority) LIKE '%president%' AND 
                     NOT LOWER(user_seniority) LIKE '%vice president%' THEN 'exec'
                ELSE 'other'
            END as seniority_group,
            CASE
                WHEN date >= '2018-01-01' AND date < '2020-01-01' THEN 'pre'
                WHEN date >= '2020-01-01' AND date <= '2021-12-31' THEN 'post'
                ELSE 'exclude'
            END as period
        FROM linkedin_panel
        WHERE companyname IS NOT NULL
          AND user_id IS NOT NULL
          AND position_role_soc IS NOT NULL
    ),

    -- Step 2: Count employees by firm/role/seniority/period
    counts AS (
        SELECT
            companyname,
            soc_code,
            seniority_group,
            period,
            COUNT(DISTINCT user_id) as n_employees
        FROM cleaned_data
        WHERE period IN ('pre', 'post')
          AND seniority_group != 'other'  -- Exclude uncategorized seniority
        GROUP BY companyname, soc_code, seniority_group, period
    ),

    -- Step 3: Get total employees by firm and period
    firm_totals AS (
        SELECT
            companyname,
            period,
            SUM(n_employees) as total_employees
        FROM counts
        GROUP BY companyname, period
    ),

    -- Step 4: Calculate shares
    shares AS (
        SELECT
            c.companyname,
            c.soc_code,
            c.seniority_group,
            c.period,
            c.n_employees,
            ft.total_employees,
            c.n_employees * 1.0 / ft.total_employees as share
        FROM counts c
        JOIN firm_totals ft
          ON c.companyname = ft.companyname
          AND c.period = ft.period
    ),

    -- Step 5: Pivot to get pre and post shares
    shares_pivot AS (
        SELECT
            companyname,
            soc_code,
            seniority_group,
            MAX(CASE WHEN period = 'pre' THEN share ELSE 0 END) as share_pre,
            MAX(CASE WHEN period = 'post' THEN share ELSE 0 END) as share_post,
            MAX(CASE WHEN period = 'pre' THEN n_employees ELSE 0 END) as n_pre,
            MAX(CASE WHEN period = 'post' THEN n_employees ELSE 0 END) as n_post
        FROM shares
        GROUP BY companyname, soc_code, seniority_group
    ),

    -- Step 6: Calculate percentage changes
    changes AS (
        SELECT
            companyname,
            soc_code,
            seniority_group,
            share_pre,
            share_post,
            n_pre,
            n_post,
            CASE
                WHEN share_pre = 0 AND share_post > 0 THEN 100
                WHEN share_pre > 0 THEN ((share_post - share_pre) / share_pre) * 100
                ELSE 0
            END as pct_change
        FROM shares_pivot
    ),

    -- Step 7: Create firm-level variables
    firm_composition AS (
        SELECT DISTINCT
            companyname
        FROM changes
    )
    
    SELECT 
        fc.companyname,
        -- Role-only variables (top 15 SOCs)
        """
    
    # Add role-only variables
    for soc in top_socs:
        query += f"""
        COALESCE(
            (SELECT SUM(pct_change) 
             FROM changes 
             WHERE companyname = fc.companyname 
               AND soc_code = '{soc}'
             GROUP BY companyname), 0
        ) as pct_chg_soc{soc},
        """
    
    # Add seniority-only variables
    for seniority in ['junior', 'senior', 'manager', 'director', 'exec']:
        query += f"""
        COALESCE(
            (SELECT SUM(pct_change) 
             FROM changes 
             WHERE companyname = fc.companyname 
               AND seniority_group = '{seniority}'
             GROUP BY companyname), 0
        ) as pct_chg_{seniority},
        """
    
    # Add key role × seniority interactions (focusing on most important combinations)
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
        COALESCE(
            (SELECT pct_change 
             FROM changes 
             WHERE companyname = fc.companyname 
               AND soc_code = '{soc}'
               AND seniority_group = '{seniority}'), 0
        ) as pct_chg_soc{soc}_{seniority},
        """
    
    # Remove trailing comma and add FROM clause
    query = query.rstrip(',\n        ') + """
    FROM firm_composition fc
    ORDER BY companyname
    """
    
    print("Loading LinkedIn panel data...")
    # Load LinkedIn data from the correct path
    linkedin_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/data/clean/linkedin_panel.parquet")
    if linkedin_path.exists():
        con.execute(f"""
            CREATE TABLE linkedin_panel AS 
            SELECT * FROM read_parquet('{linkedin_path}')
        """)
        print(f"Loaded LinkedIn panel data from {linkedin_path}")
    else:
        # For testing, create sample data
        print(f"Warning: LinkedIn panel data not found at {linkedin_path}")
        print("Creating sample data for testing...")
        con.execute("""
            CREATE TABLE linkedin_panel AS
            SELECT 
                'company_' || (i % 1000) as companyname,
                'user_' || i as user_id,
                DATE '2018-01-01' + INTERVAL (i % 1460) DAY as date,
                CASE (i % 15)
                    WHEN 0 THEN '15-1132'
                    WHEN 1 THEN '13-2011'
                    WHEN 2 THEN '11-9111'
                    WHEN 3 THEN '13-1111'
                    WHEN 4 THEN '41-2031'
                    WHEN 5 THEN '11-1021'
                    WHEN 6 THEN '13-1071'
                    WHEN 7 THEN '13-1161'
                    WHEN 8 THEN '15-1134'
                    WHEN 9 THEN '13-1051'
                    WHEN 10 THEN '11-3021'
                    WHEN 11 THEN '13-1041'
                    WHEN 12 THEN '13-1199'
                    WHEN 13 THEN '11-9021'
                    ELSE '11-9041'
                END as position_role_soc,
                CASE (i % 5)
                    WHEN 0 THEN 'Junior Analyst'
                    WHEN 1 THEN 'Senior Developer'
                    WHEN 2 THEN 'Manager'
                    WHEN 3 THEN 'Director'
                    ELSE 'Vice President'
                END as user_seniority
            FROM generate_series(1, 100000) as s(i)
        """)
    
    print("Running composition analysis...")
    # Execute the main query and save results
    result = con.execute(query).fetchdf()
    
    # Save to CSV
    output_path = Path("/Users/saul/Dropbox/Remote Work Startups/main/results/raw/composition_role_seniority_full.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    print(f"Saved composition variables to {output_path}")
    
    # Display summary statistics
    print("\nSummary of composition variables:")
    print(f"Number of firms: {len(result)}")
    print(f"Number of variables: {len(result.columns) - 1}")  # Minus companyname
    
    # Show sample of results
    print("\nSample of results (first 5 firms, first 5 variables):")
    print(result.iloc[:5, :6])
    
    con.close()

if __name__ == "__main__":
    main()