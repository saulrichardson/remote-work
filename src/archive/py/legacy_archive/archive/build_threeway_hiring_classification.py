#!/usr/bin/env python3
"""
Build three-way hiring classification to test remote vs geographic expansion.

This script classifies all post-2019 hires into three categories:
1. Legacy MSA - hires in traditional office locations (2019-H2 baseline)
2. New MSA - hires in new physical locations  
3. Remote - hires without MSA designation (cbsa='remote')

Key metrics calculated:
- share_legacy_msa: legacy MSA hires / total hires
- share_new_msa: new MSA hires / total hires  
- share_remote: remote hires / total hires
- total_dispersion: (new MSA + remote hires) / total hires
- remote_substitution_rate: remote / (remote + new MSA)

Outputs:
--------
data/clean/firm_threeway_hiring_metrics.csv
    - firm, yh, and all share metrics
    
data/clean/threeway_hiring_summary.csv
    - Summary statistics by period and treatment

Usage:
------
python py/build_threeway_hiring_classification.py
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import duckdb
    import pandas as pd
    import numpy as np
except ImportError:
    print("ERROR: Required packages missing. Install with: pip install duckdb pandas numpy")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROC = DATA / "processed"

# Input
FIRM_ENTRY_HIRES = PROC / "firm_entry_hires.parquet"
LEGACY_LOCATIONS = PROC / "firm_legacy_locations_clean.csv"
FIRM_PANEL = PROC / "firm_panel.dta"

# Output
THREEWAY_METRICS = PROC / "firm_threeway_hiring_metrics.csv"
THREEWAY_SUMMARY = PROC / "threeway_hiring_summary.csv"

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
    return parser.parse_args()


def build_threeway_classification(debug=False):
    """
    Main pipeline to build three-way hiring classification.
    """
    con = duckdb.connect()
    
    # Configure DuckDB
    con.execute("SET enable_progress_bar = true;")
    
    print(f"\n{'='*70}")
    print(f"Building Three-Way Hiring Classification")
    print(f"{'='*70}")
    print(f"Categories: Legacy MSA | New MSA | Remote")
    print(f"Post-period: {YH_2020H1} (2020-H1) onwards")
    
    # -----------------------------------------------------------------------
    # Step 1: Load data
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 1: Loading data...")
    
    # Check files exist
    if not FIRM_ENTRY_HIRES.exists():
        raise FileNotFoundError(
            f"Firm-entry hires not found at {FIRM_ENTRY_HIRES}. Run build_firm_entry_hires.py first."
        )
    if not LEGACY_LOCATIONS.exists():
        raise FileNotFoundError(f"Legacy locations not found. Run build_firm_legacy_locations.py first.")
    
    # Load firm-entry hires (already post-2019 by construction)
    con.execute(f"""
        CREATE TEMP VIEW hires AS
        SELECT 
            lower(firm) as firm,
            CAST(yh AS INTEGER) as yh,
            CAST(cbsa AS VARCHAR) as cbsa,
            CAST(is_remote AS INTEGER) as is_remote,
            CAST(hires AS INTEGER) as hires,
            COALESCE(CAST(new_location_entries AS INTEGER), 0) as new_location_entries
        FROM read_parquet('{FIRM_ENTRY_HIRES}');
    """)

    stats = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(*) as n_rows,
            SUM(hires) as total_hires,
            SUM(CASE WHEN is_remote = 1 THEN hires ELSE 0 END) as remote_hires
        FROM hires
    """).fetchone()
    
    print(f"  Firm-entry hires loaded:")
    print(f"    Firms: {stats[0]:,}")
    print(f"    Rows: {stats[1]:,}")
    print(f"    Total hires: {stats[2]:,}")
    print(f"    Remote hires: {stats[3]:,}")
    
    # Load legacy locations (with explicit types to handle company names with commas)
    con.execute(f"""
        CREATE TEMP VIEW legacy_locations AS
        SELECT 
            lower(firm) as firm,
            CAST(cbsa AS VARCHAR) as cbsa,
            is_legacy
        FROM read_csv_auto('{LEGACY_LOCATIONS}', 
            header=True,
            types={{'firm': 'VARCHAR', 'cbsa': 'VARCHAR', 'is_legacy': 'INTEGER'}},
            strict_mode=false,
            null_padding=true)
        WHERE is_legacy = 1;
    """)
    
    legacy_stats = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(*) as n_locations
        FROM legacy_locations
    """).fetchone()
    
    print(f"  Legacy locations loaded:")
    print(f"    Firms with legacy offices: {legacy_stats[0]:,}")
    print(f"    Total legacy locations: {legacy_stats[1]:,}")
    
    # -----------------------------------------------------------------------
    # Step 2: Classify post-2019 hires
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 2: Classifying post-2019 hires...")
    
    con.execute(f"""
        CREATE TEMP VIEW hire_classification AS
        SELECT 
            h.firm,
            h.yh,
            h.cbsa,
            h.is_remote,
            h.hires as hires,
            h.new_location_entries,
            CASE 
                WHEN h.is_remote = 1 THEN 'remote'
                WHEN leg.is_legacy = 1 THEN 'legacy_msa'
                ELSE 'new_msa'
            END as hire_type
        FROM hires h
        LEFT JOIN legacy_locations leg
            ON h.firm = leg.firm 
            AND h.cbsa = leg.cbsa
        WHERE h.hires > 0;
    """)
    
    # Check classification distribution
    class_dist = con.execute("""
        SELECT 
            hire_type,
            COUNT(*) as n_obs,
            SUM(hires) as total_hires,
            ROUND(100.0 * SUM(hires) / SUM(SUM(hires)) OVER (), 2) as pct_hires
        FROM hire_classification
        GROUP BY hire_type
        ORDER BY hire_type
    """).fetchall()
    
    print("\n  Hire classification distribution:")
    for row in class_dist:
        print(f"    {row[0]:12s}: {row[2]:>12,} hires ({row[3]:>5}%)")
    
    # -----------------------------------------------------------------------
    # Step 3: Aggregate to firm × time level
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 3: Aggregating to firm × time...")
    
    con.execute("""
        CREATE TEMP VIEW firm_period_hires AS
        SELECT 
            firm,
            yh,
            SUM(hires) as total_hires,
            SUM(CASE WHEN hire_type = 'legacy_msa' THEN hires ELSE 0 END) as legacy_msa_hires,
            SUM(CASE WHEN hire_type = 'new_msa' THEN hires ELSE 0 END) as new_msa_hires,
            SUM(CASE WHEN hire_type = 'remote' THEN hires ELSE 0 END) as remote_hires,
            -- Count of new markets entered this period (first entries only, physical)
            SUM(new_location_entries) as n_new_locations
        FROM hire_classification
        GROUP BY firm, yh;
    """)
    
    # Calculate shares and derived metrics (compute unrounded for validation, round for output)
    con.execute("""
        CREATE TEMP VIEW threeway_metrics_calc AS
        SELECT 
            firm,
            yh,
            total_hires,
            legacy_msa_hires,
            new_msa_hires,
            remote_hires,
            n_new_locations,
            (legacy_msa_hires::DOUBLE / total_hires) as share_legacy_msa_unr,
            (new_msa_hires::DOUBLE / total_hires) as share_new_msa_unr,
            (remote_hires::DOUBLE / total_hires) as share_remote_unr
        FROM firm_period_hires
        WHERE total_hires > 0;
        
        CREATE TEMP TABLE threeway_metrics AS
        SELECT 
            firm,
            yh,
            total_hires,
            legacy_msa_hires,
            new_msa_hires,
            remote_hires,
            n_new_locations,
            ROUND(share_legacy_msa_unr, 4) AS share_legacy_msa,
            ROUND(share_new_msa_unr, 4)     AS share_new_msa,
            ROUND(share_remote_unr, 4)      AS share_remote,
            ROUND(share_new_msa_unr + share_remote_unr, 4) AS total_dispersion,
            CASE WHEN (share_new_msa_unr + share_remote_unr) > 0
                 THEN ROUND(remote_hires::DOUBLE / (new_msa_hires + remote_hires), 4)
                 ELSE NULL END AS remote_substitution_rate
        FROM threeway_metrics_calc;
    """)
    
    # Get summary stats
    summary = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(*) as n_obs,
            AVG(share_legacy_msa) as avg_legacy,
            AVG(share_new_msa) as avg_new_msa,
            AVG(share_remote) as avg_remote,
            AVG(total_dispersion) as avg_dispersion
        FROM threeway_metrics
    """).fetchone()
    
    print(f"\n  Firm-period metrics created:")
    print(f"    Firms: {summary[0]:,}")
    print(f"    Observations: {summary[1]:,}")
    print(f"\n  Average shares across all post-2019 firm-periods:")
    print(f"    Legacy MSA: {summary[2]:.1%}")
    print(f"    New MSA: {summary[3]:.1%}")
    print(f"    Remote: {summary[4]:.1%}")
    print(f"    Total dispersion: {summary[5]:.1%}")
    
    # -----------------------------------------------------------------------
    # Step 4: Check share validity
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 4: Validating shares sum to 1.0...")
    
    con.execute("""
        CREATE TEMP VIEW share_check AS
        SELECT 
            firm,
            yh,
            (share_legacy_msa_unr + share_new_msa_unr + share_remote_unr) as total_share,
            ABS((share_legacy_msa_unr + share_new_msa_unr + share_remote_unr) - 1.0) as deviation
        FROM threeway_metrics_calc;
    """)
    
    check = con.execute("""
        SELECT 
            MAX(deviation) as max_deviation,
            AVG(deviation) as avg_deviation,
            SUM(CASE WHEN deviation > 0.01 THEN 1 ELSE 0 END) as problematic_obs
        FROM share_check
    """).fetchone()
    
    print(f"  Share validation:")
    print(f"    Max deviation from 1.0: {check[0]:.6f}")
    print(f"    Avg deviation: {check[1]:.6f}")
    print(f"    Observations with >1% deviation: {check[2]}")
    
    if check[2] > 0:
        print("  WARNING: Some observations don't sum to 1.0")
    else:
        print("  ✓ All shares sum to 1.0")
    
    # -----------------------------------------------------------------------
    # Step 5: Save outputs
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 5: Saving outputs...")
    
    # Main metrics file
    metrics_df = con.execute("SELECT * FROM threeway_metrics ORDER BY firm, yh").df()
    metrics_df.to_csv(THREEWAY_METRICS, index=False)
    print(f"  ✓ Saved {THREEWAY_METRICS.name}")
    print(f"    Rows: {len(metrics_df):,}")
    
    # Summary by period
    summary_df = con.execute("""
        SELECT 
            yh,
            COUNT(DISTINCT firm) as n_firms,
            AVG(share_legacy_msa) as avg_share_legacy_msa,
            AVG(share_new_msa) as avg_share_new_msa,
            AVG(share_remote) as avg_share_remote,
            AVG(total_dispersion) as avg_total_dispersion,
            AVG(remote_substitution_rate) as avg_remote_substitution,
            STDDEV(share_legacy_msa) as std_share_legacy_msa,
            STDDEV(share_new_msa) as std_share_new_msa,
            STDDEV(share_remote) as std_share_remote
        FROM threeway_metrics
        GROUP BY yh
        ORDER BY yh
    """).df()
    
    summary_df.to_csv(THREEWAY_SUMMARY, index=False)
    print(f"  ✓ Saved {THREEWAY_SUMMARY.name}")
    
    # -----------------------------------------------------------------------
    # Step 6: Show trends over time
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 6: Trends over time...")
    
    print("\n  Average shares by half-year:")
    print("  " + "─"*60)
    print(f"  {'Period':<10} {'Legacy MSA':<12} {'New MSA':<12} {'Remote':<12} {'Total Disp':<12}")
    print("  " + "─"*60)
    
    for _, row in summary_df.iterrows():
        yh = int(row['yh'])
        year = yh // 2
        half = "H1" if yh % 2 == 0 else "H2"
        period = f"{year}-{half}"
        print(f"  {period:<10} {row['avg_share_legacy_msa']:>11.1%} {row['avg_share_new_msa']:>12.1%} {row['avg_share_remote']:>12.1%} {row['avg_total_dispersion']:>12.1%}")
    
    print("\n" + "="*70)
    print("Three-way classification complete!")
    print("="*70)
    
    return metrics_df


if __name__ == "__main__":
    args = parse_args()
    build_threeway_classification(debug=args.debug)
