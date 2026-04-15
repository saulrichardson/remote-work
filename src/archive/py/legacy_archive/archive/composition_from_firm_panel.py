#!/usr/bin/env python3
"""
Create role × seniority composition from firm-level panel data
Uses existing processed data to create the variables
"""

import pandas as pd
import numpy as np
import duckdb
import os

# Use DuckDB to efficiently process firm panel data
con = duckdb.connect()

# Check what firm-level data we have
print("Checking available firm-level data...")

# Load firm SOC panel (has role breakdown by firm)
if os.path.exists('data/clean/firm_soc_panel_enriched.csv'):
    print("Loading firm SOC panel...")
    firm_soc = pd.read_csv('data/clean/firm_soc_panel_enriched.csv')
    print(f"Shape: {firm_soc.shape}")
    print(f"Columns: {firm_soc.columns.tolist()[:10]}")
    
    # Create composition measures from this data
    con.execute("CREATE TABLE firm_soc AS SELECT * FROM firm_soc")
    
    # Calculate percentage changes by SOC
    query = """
    WITH period_data AS (
        SELECT 
            companyname,
            soc4 as soc_code,
            yh,
            CASE 
                WHEN yh < 4040 THEN 'pre'  -- Before 2020H1
                WHEN yh >= 4040 AND yh <= 4044 THEN 'post'  -- 2020H1 to 2021H2
                ELSE 'excluded'
            END as period,
            headcount
        FROM firm_soc
        WHERE headcount > 0
    ),
    
    aggregated AS (
        SELECT 
            companyname,
            soc_code,
            period,
            AVG(headcount) as avg_headcount
        FROM period_data
        WHERE period IN ('pre', 'post')
        GROUP BY companyname, soc_code, period
    ),
    
    changes AS (
        SELECT 
            companyname,
            soc_code,
            MAX(CASE WHEN period = 'pre' THEN avg_headcount ELSE 0 END) as pre_count,
            MAX(CASE WHEN period = 'post' THEN avg_headcount ELSE 0 END) as post_count
        FROM aggregated
        GROUP BY companyname, soc_code
    )
    
    SELECT 
        companyname,
        'pct_chg_soc' || soc_code as variable,
        CASE 
            WHEN pre_count > 0 THEN 100.0 * (post_count - pre_count) / pre_count
            WHEN post_count > 0 THEN 100.0
            ELSE 0
        END as value
    FROM changes
    WHERE soc_code IN (
        SELECT soc_code 
        FROM period_data 
        GROUP BY soc_code 
        ORDER BY SUM(headcount) DESC 
        LIMIT 15
    )
    """
    
    results = con.execute(query).fetchdf()
    
    # Pivot to wide format
    results_wide = results.pivot(index='companyname', columns='variable', values='value').reset_index()
    results_wide = results_wide.fillna(0)
    
    # Add lowercase company name
    results_wide['companyname_lower'] = results_wide['companyname'].str.lower()
    
    # Save
    output_file = 'results/raw/composition_role_only.dta'
    results_wide.to_stata(output_file, write_index=False)
    print(f"\nSaved role composition to: {output_file}")
    print(f"Shape: {results_wide.shape}")
    print(f"Variables created: {[c for c in results_wide.columns if c.startswith('pct_chg')]}")

# For seniority, we need to simulate since we don't have that breakdown
print("\nNote: Seniority breakdown requires individual-level LinkedIn data.")
print("Use the DuckDB script on HPC for full role × seniority analysis.")

con.close()