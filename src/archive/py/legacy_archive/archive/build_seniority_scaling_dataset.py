#!/usr/bin/env python3
"""
Build dataset measuring % growth in scaling by seniority level
Similar to role_k7 analysis but using seniority (1-4 scale)
"""

import pandas as pd
import numpy as np
import duckdb
from pathlib import Path
import time
import argparse

def build_seniority_scaling_dataset(input_path=None, output_path=None, sample_size=None):
    """
    Build a dataset showing % growth in employee count by seniority level
    
    Seniority levels:
    1 = Entry level (junior, associate)
    2 = Mid-level (senior individual contributors)
    3 = Management level
    4 = Senior management/executive level
    """
    start_time = time.time()
    
    # Default paths
    if input_path is None:
        input_path = "/Users/saul/Dropbox/Remote Work Startups/main/data/raw/Scoop_workers_positions.csv"
    if output_path is None:
        output_path = "/Users/saul/Dropbox/Remote Work Startups/main/data/clean/seniority_scaling_growth.csv"
    
    print("Building Seniority Scaling Growth Dataset")
    print("="*60)
    print(f"Input file: {input_path}")
    print(f"Reading full dataset...")
    
    # Connect to DuckDB
    con = duckdb.connect(':memory:')
    con.execute("SET memory_limit='8GB'")
    con.execute("SET threads TO 8")
    
    # Build the query
    sample_clause = f"LIMIT {sample_size}" if sample_size else ""
    
    query = f"""
    -- First, create employee counts by company, seniority, and half-year
    WITH employee_periods AS (
        SELECT 
            companyname,
            user_id,
            CAST(seniority AS INTEGER) as seniority_level,
            CAST(start_date AS DATE) as start_dt,
            COALESCE(CAST(end_date AS DATE), DATE '2023-12-31') as end_dt
        FROM read_csv_auto('{input_path}', strict_mode=false, null_padding=true, ignore_errors=true)
        WHERE companyname IS NOT NULL 
          AND seniority IS NOT NULL
          AND seniority IN (1, 2, 3, 4)  -- Valid seniority levels only
          AND start_date IS NOT NULL
        {sample_clause}
    ),
    
    -- Generate half-year periods for each employee
    period_counts AS (
        SELECT 
            companyname,
            seniority_level,
            CAST(YEAR(period_dt) AS VARCHAR) || 
                CASE WHEN MONTH(period_dt) <= 6 THEN 'H1' ELSE 'H2' END as year_half,
            COUNT(DISTINCT user_id) as employee_count
        FROM (
            SELECT 
                companyname,
                user_id,
                seniority_level,
                UNNEST(generate_series(
                    DATE_TRUNC('month', start_dt),
                    DATE_TRUNC('month', end_dt),
                    INTERVAL '1 month'
                )) as period_dt
            FROM employee_periods
        ) monthly
        WHERE YEAR(period_dt) BETWEEN 2018 AND 2023
        GROUP BY companyname, seniority_level, year_half
    ),
    
    -- Calculate growth rates and total employees per firm-period
    growth_rates AS (
        SELECT 
            companyname,
            seniority_level,
            year_half,
            employee_count,
            LAG(employee_count) OVER (
                PARTITION BY companyname, seniority_level 
                ORDER BY year_half
            ) as prev_count,
            SUM(employee_count) OVER (
                PARTITION BY companyname, year_half
            ) as total_employees_yh,
            -- Calculate growth rate
            CASE 
                WHEN LAG(employee_count) OVER (
                    PARTITION BY companyname, seniority_level 
                    ORDER BY year_half
                ) > 0
                THEN ROUND(
                    1.0 * (employee_count - LAG(employee_count) OVER (
                        PARTITION BY companyname, seniority_level 
                        ORDER BY year_half
                    )) / LAG(employee_count) OVER (
                        PARTITION BY companyname, seniority_level 
                        ORDER BY year_half
                    ), 4
                )
                ELSE NULL
            END as pct_growth_seniority
        FROM period_counts
    ),
    
    -- Add year and half columns and compute shares
    labeled_growth AS (
        SELECT 
            *,
            -- Extract year and half as separate columns
            CAST(SUBSTRING(year_half, 1, 4) AS INTEGER) as year,
            CAST(SUBSTRING(year_half, 6, 1) AS INTEGER) as half,
            CASE WHEN total_employees_yh > 0
                 THEN ROUND(1.0 * employee_count / total_employees_yh, 6)
                 ELSE NULL END as seniority_share,
            CASE WHEN total_employees_yh > 0
                 THEN ROUND(
                      1.0 * employee_count / total_employees_yh
                      - LAG(1.0 * employee_count / total_employees_yh) OVER (
                            PARTITION BY companyname, seniority_level
                            ORDER BY year_half
                        )
                 , 6)
                 ELSE NULL END as d_seniority_share
        FROM growth_rates
        WHERE pct_growth_seniority IS NOT NULL
          AND employee_count >= 5  -- Filter out very small teams
    )
    
    SELECT * FROM labeled_growth
    ORDER BY companyname, seniority_level, year_half
    """
    
    # First count total rows in source file
    count_query = f"""
    SELECT COUNT(*) as total_rows,
           COUNT(DISTINCT companyname) as unique_companies,
           COUNT(DISTINCT user_id) as unique_users,
           COUNT(DISTINCT seniority) as unique_seniority_levels
    FROM read_csv_auto('{input_path}', strict_mode=false, null_padding=true, ignore_errors=true)
    WHERE companyname IS NOT NULL AND seniority IN (1, 2, 3, 4)
    """
    
    print("\nCounting source data...")
    counts = con.execute(count_query).fetchone()
    print(f"Source file contains:")
    print(f"  - Total rows with valid seniority: {counts[0]:,}")
    print(f"  - Unique companies: {counts[1]:,}")
    print(f"  - Unique users: {counts[2]:,}")
    print(f"  - Seniority levels found: {counts[3]}")
    
    print("\nCalculating growth rates...")
    df_growth = con.execute(query).df()
    
    # Close DuckDB connection
    con.close()
    
    # Save outputs
    output_path = Path(output_path)
    output_path.parent.mkdir(exist_ok=True, parents=True)
    
    # Save main growth dataset
    print(f"\nSaving company-level growth data to: {output_path}")
    df_growth.to_csv(output_path, index=False)
    
    # Also save in Stata format for econometric analysis
    stata_path = output_path.with_suffix('.dta')
    print(f"Saving Stata file to: {stata_path}")
    try:
        df_growth.to_stata(stata_path, write_index=False)
        print(f"Stata file saved successfully")
    except UnicodeEncodeError:
        print(f"Warning: Could not save Stata file due to Unicode characters")
        print(f"CSV file saved successfully at: {output_path}")
    
    elapsed = time.time() - start_time
    print(f"\nProcessing completed in {elapsed:.1f} seconds")
    print(f"\nFINAL OUTPUT STATISTICS:")
    print(f"  - Total growth observations: {len(df_growth):,}")
    print(f"  - Unique companies: {df_growth['companyname'].nunique():,}")
    print(f"  - Seniority levels: {sorted(df_growth['seniority_level'].unique())}")
    print(f"  - Date range: {df_growth['year_half'].min()} to {df_growth['year_half'].max()}")
    print(f"\nData reduction: {counts[0]:,} rows → {len(df_growth):,} growth rates")
    
    return df_growth

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build seniority scaling growth dataset')
    parser.add_argument('--input', type=str, help='Path to LinkedIn data')
    parser.add_argument('--output', type=str, help='Output path for results')
    parser.add_argument('--sample', type=int, help='Number of rows to sample (for testing)')
    
    args = parser.parse_args()
    
    build_seniority_scaling_dataset(
        input_path=args.input,
        output_path=args.output,
        sample_size=args.sample
    )
