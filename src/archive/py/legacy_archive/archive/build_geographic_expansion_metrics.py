#!/usr/bin/env python3
"""
Build geographic expansion metrics based on post-2019 hiring patterns.

This script:
1. Loads the legacy location sets from Phase 1
2. Identifies new hires (joins) in post-2019 periods
3. Flags whether hires are in legacy vs new geographies
4. Aggregates to firm×time metrics for regression analysis

Outputs:
--------
data/clean/firm_geographic_expansion.csv
    - firm, yh, total_hires, new_geo_hires, share_new_geo, n_new_locations

data/clean/firm_geographic_expansion_detail.csv  
    - firm, cbsa, yh, hires, is_legacy, is_new_location

Usage:
------
python py/build_geographic_expansion_metrics.py [--min-employees 100] [--min-share 0.10]
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import duckdb
    import pandas as pd
except ImportError:
    print("ERROR: Required packages missing. Install with: pip install duckdb pandas")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROC = DATA / "processed"

# Input
LINKEDIN_PANEL = PROC / "linkedin_panel.parquet"
LEGACY_LOCATIONS = PROC / "firm_legacy_locations_clean.csv"
LEGACY_SUMMARY = PROC / "firm_legacy_summary.csv"

# Output
EXPANSION_METRICS = PROC / "firm_geographic_expansion.csv"
EXPANSION_DETAIL = PROC / "firm_geographic_expansion_detail.csv"
QA_LOG = ROOT / "results" / "geographic_expansion_qa.log"

# Constants
YH_2019H2 = 2019 * 2 + 1  # 4039 - last pre-period
YH_2020H1 = 2020 * 2      # 4040 - first post-period

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed debugging output"
    )
    parser.add_argument(
        "--sample-firms",
        type=int,
        help="Process only N firms for testing"
    )
    return parser.parse_args()


def build_expansion_metrics(debug=False, sample_firms=None):
    """
    Main pipeline to build geographic expansion metrics.
    """
    con = duckdb.connect()
    
    # Configure DuckDB
    con.execute("SET enable_progress_bar = true;")
    
    print(f"\n{'='*70}")
    print(f"Building Geographic Expansion Metrics")
    print(f"{'='*70}")
    print(f"Post-period: {YH_2020H1} (2020-H1) onwards")
    
    # -----------------------------------------------------------------------
    # Step 1: Load legacy locations
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 1: Loading legacy location sets...")
    
    if not LEGACY_LOCATIONS.exists():
        print(f"ERROR: Legacy locations file not found at {LEGACY_LOCATIONS}")
        print("Run build_firm_legacy_locations.py first")
        return False
    
    # Load legacy locations (only those marked as legacy)
    # Use quote and escape settings to handle company names with commas
    con.execute(f"""
        CREATE OR REPLACE TABLE legacy_sets AS
        SELECT DISTINCT
            firm,
            cbsa
        FROM read_csv('{LEGACY_LOCATIONS}', 
            AUTO_DETECT=true,
            quote='"',
            escape='"',
            ignore_errors=true)
        WHERE is_legacy = 1
    """)
    
    # Check coverage
    legacy_stats = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(*) as n_legacy_pairs,
            AVG(cnt) as avg_legacy_per_firm
        FROM (
            SELECT firm, COUNT(*) as cnt
            FROM legacy_sets
            GROUP BY firm
        )
    """).fetchone()
    
    print(f"  Loaded legacy sets for {legacy_stats[0]:,} firms")
    print(f"  Total legacy firm×location pairs: {legacy_stats[1]:,}")
    print(f"  Average legacy locations per firm: {legacy_stats[2]:.1f}")
    
    # -----------------------------------------------------------------------
    # Step 2: Load post-2019 hiring data
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 2: Loading post-2019 hiring data...")
    
    sample_clause = ""
    if sample_firms:
        # Get top N firms by size for testing
        top_firms = con.execute(f"""
            SELECT DISTINCT firm 
            FROM read_csv_auto('{LEGACY_SUMMARY}')
            ORDER BY total_emp_2019 DESC
            LIMIT {sample_firms}
        """).fetchall()
        firm_list = "', '".join([f[0] for f in top_firms])
        sample_clause = f"AND LOWER(companyname) IN ('{firm_list}')"
        print(f"  SAMPLE MODE: Processing {sample_firms} largest firms")
    
    # Load hiring data (joins) from post-2019 periods
    con.execute(f"""
        CREATE OR REPLACE TABLE post_2019_hiring AS
        SELECT 
            LOWER(companyname) as firm,
            cbsa,
            yh,
            SUM(joins) as hires
        FROM parquet_scan('{LINKEDIN_PANEL}')
        WHERE yh >= {YH_2020H1}
            AND joins > 0
            {sample_clause}
        GROUP BY 1, 2, 3
    """)
    
    hire_stats = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(DISTINCT cbsa) as n_cbsas,
            COUNT(DISTINCT yh) as n_periods,
            SUM(hires) as total_hires,
            MIN(yh) as min_yh,
            MAX(yh) as max_yh
        FROM post_2019_hiring
    """).fetchone()
    
    print(f"\nPost-2019 hiring data:")
    print(f"  - Firms: {hire_stats[0]:,}")
    print(f"  - CBSAs: {hire_stats[1]:,}")
    print(f"  - Time periods: {hire_stats[2]} ({hire_stats[4]} to {hire_stats[5]})")
    print(f"  - Total hires: {hire_stats[3]:,}")
    
    # -----------------------------------------------------------------------
    # Step 3: Flag legacy vs new geography hires
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 3: Flagging legacy vs new geography hires...")
    
    # Join hiring data with legacy sets
    con.execute("""
        CREATE OR REPLACE TABLE hiring_flagged AS
        SELECT 
            h.firm,
            h.cbsa,
            h.yh,
            h.hires,
            CASE 
                WHEN l.cbsa IS NOT NULL THEN 1 
                ELSE 0 
            END as is_legacy,
            CASE 
                WHEN l.cbsa IS NULL THEN 1 
                ELSE 0 
            END as is_new_geography
        FROM post_2019_hiring h
        LEFT JOIN legacy_sets l 
            ON h.firm = l.firm 
            AND h.cbsa = l.cbsa
    """)
    
    # Summary of flagged hires
    flag_summary = con.execute("""
        SELECT 
            SUM(hires) as total_hires,
            SUM(CASE WHEN is_legacy = 1 THEN hires ELSE 0 END) as legacy_hires,
            SUM(CASE WHEN is_new_geography = 1 THEN hires ELSE 0 END) as new_geo_hires,
            COUNT(DISTINCT CASE WHEN is_new_geography = 1 THEN firm || '|' || cbsa END) as new_firm_cbsa_pairs
        FROM hiring_flagged
    """).fetchone()
    
    print(f"\nHiring breakdown:")
    print(f"  - Total post-2019 hires: {flag_summary[0]:,}")
    print(f"  - Hires in legacy locations: {flag_summary[1]:,} ({flag_summary[1]/flag_summary[0]*100:.1f}%)")
    print(f"  - Hires in NEW geographies: {flag_summary[2]:,} ({flag_summary[2]/flag_summary[0]*100:.1f}%)")
    print(f"  - New firm×location pairs entered: {flag_summary[3]:,}")
    
    # -----------------------------------------------------------------------
    # Step 4: Aggregate to firm×time level
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 4: Aggregating to firm×time metrics...")
    
    con.execute("""
        CREATE OR REPLACE TABLE firm_expansion_metrics AS
        SELECT 
            firm,
            yh,
            SUM(hires) as total_hires,
            SUM(CASE WHEN is_new_geography = 1 THEN hires ELSE 0 END) as new_geo_hires,
            ROUND(
                SUM(CASE WHEN is_new_geography = 1 THEN hires ELSE 0 END)::FLOAT / 
                NULLIF(SUM(hires), 0), 
                4
            ) as share_new_geo,
            COUNT(DISTINCT CASE WHEN is_new_geography = 1 THEN cbsa END) as n_new_locations,
            COUNT(DISTINCT cbsa) as n_total_locations
        FROM hiring_flagged
        GROUP BY firm, yh
        ORDER BY firm, yh
    """)
    
    # Summary statistics
    metrics_summary = con.execute("""
        SELECT 
            COUNT(*) as n_observations,
            COUNT(DISTINCT firm) as n_firms,
            AVG(share_new_geo) as avg_share_new,
            MIN(share_new_geo) as min_share,
            MAX(share_new_geo) as max_share,
            AVG(n_new_locations) as avg_new_locs
        FROM firm_expansion_metrics
        WHERE total_hires > 0
    """).fetchone()
    
    print(f"\nFirm×time expansion metrics:")
    print(f"  - Observations: {metrics_summary[0]:,}")
    print(f"  - Unique firms: {metrics_summary[1]:,}")
    print(f"  - Average share in new geography: {metrics_summary[2]:.1%}")
    print(f"  - Range: {metrics_summary[3]:.1%} to {metrics_summary[4]:.1%}")
    print(f"  - Average new locations per firm-period: {metrics_summary[5]:.2f}")
    
    # -----------------------------------------------------------------------
    # Step 5: Analyze trends over time
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 5: Analyzing temporal trends...")
    
    trends = con.execute("""
        SELECT 
            yh,
            yh/2 as year,
            COUNT(DISTINCT firm) as n_firms,
            AVG(share_new_geo) as avg_share_new_geo,
            SUM(new_geo_hires) as total_new_geo_hires,
            SUM(total_hires) as total_hires
        FROM firm_expansion_metrics
        WHERE total_hires > 0
        GROUP BY yh
        ORDER BY yh
    """).fetchall()
    
    print(f"\nGeographic expansion by period:")
    print(f"  {'Year-Half':>10} | {'Firms':>6} | {'New Geo Share':>13} | {'New/Total Hires':>20}")
    print(f"  {'-'*10} | {'-'*6} | {'-'*13} | {'-'*20}")
    
    for yh, year, firms, share, new_hires, total in trends[:10]:  # First 10 periods
        year_str = f"{int(year)}-H{1 if yh % 2 == 1 else 2}"
        print(f"  {year_str:>10} | {firms:>6,} | {share:>13.1%} | {new_hires:>8,}/{total:>10,}")
    
    # -----------------------------------------------------------------------
    # Step 6: Examples and quality checks
    # -----------------------------------------------------------------------
    if debug:
        print(f"\n{'─'*50}")
        print("Step 6: Example firms...")
        
        # Look at specific large firms
        examples = con.execute("""
            SELECT 
                firm,
                AVG(share_new_geo) as avg_share_new,
                SUM(new_geo_hires) as total_new_hires,
                SUM(total_hires) as total_hires,
                COUNT(DISTINCT CASE WHEN n_new_locations > 0 THEN yh END) as periods_with_new
            FROM firm_expansion_metrics
            GROUP BY firm
            ORDER BY SUM(total_hires) DESC
            LIMIT 10
        """).fetchall()
        
        print("\nTop 10 firms by hiring volume:")
        print(f"  {'Firm':30s} | {'Avg New%':>8} | {'New Hires':>10} | {'Total':>10} | New CBSAs")
        print(f"  {'-'*30} | {'-'*8} | {'-'*10} | {'-'*10} | {'-'*10}")
        
        for firm, avg_share, new_h, total_h, new_cbsas in examples:
            print(f"  {firm[:30]:30s} | {avg_share:>8.1%} | {new_h:>10,} | {total_h:>10,} | {new_cbsas:>10}")
    
    # -----------------------------------------------------------------------
    # Step 7: Write outputs
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 7: Writing output files...")
    
    # Write main metrics file
    con.execute(f"""
        COPY firm_expansion_metrics
        TO '{EXPANSION_METRICS}'
        WITH (HEADER, DELIMITER ',')
    """)
    print(f"  ✓ {EXPANSION_METRICS}")
    
    # Write detailed file
    con.execute(f"""
        COPY hiring_flagged
        TO '{EXPANSION_DETAIL}'
        WITH (HEADER, DELIMITER ',')
    """)
    print(f"  ✓ {EXPANSION_DETAIL}")
    
    # Write QA log
    QA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(QA_LOG, 'w') as f:
        f.write(f"Geographic Expansion Analysis QA Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"{'='*70}\n\n")
        
        f.write(f"Summary:\n")
        f.write(f"  - Firms analyzed: {metrics_summary[1]:,}\n")
        f.write(f"  - Time periods: {YH_2020H1} to {hire_stats[5]}\n")
        f.write(f"  - Total post-2019 hires: {flag_summary[0]:,}\n")
        f.write(f"  - Hires in new geographies: {flag_summary[2]:,} ({flag_summary[2]/flag_summary[0]*100:.1f}%)\n")
        f.write(f"  - Average firm share in new geo: {metrics_summary[2]:.1%}\n\n")
        
        f.write("Temporal Trends:\n")
        for yh, year, firms, share, new_hires, total in trends[:10]:
            year_str = f"{int(year)}-H{1 if yh % 2 == 1 else 2}"
            f.write(f"  {year_str}: {share:.1%} of hires in new geography ({new_hires:,}/{total:,})\n")
    
    print(f"  ✓ {QA_LOG}")
    
    print(f"\n{'='*70}")
    print("✅ Geographic expansion metrics complete!")
    print(f"{'='*70}\n")
    
    con.close()
    return True


def main():
    """Main entry point."""
    args = parse_args()
    
    success = build_expansion_metrics(
        debug=args.debug,
        sample_firms=args.sample_firms
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()