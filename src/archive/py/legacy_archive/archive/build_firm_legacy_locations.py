#!/usr/bin/env python3
"""
Build each firm's set of "legacy office locations" based on 2019-H2 employment.

A location qualifies as a legacy office if it meets EITHER:
- Has ≥ min_employees (default: 100)
- Has ≥ min_share of firm employment (default: 0.10 = 10%)

This creates the baseline geographic footprint used to identify whether
post-2019 hires are in "new" vs "legacy" markets.

Outputs:
--------
data/clean/firm_legacy_locations.csv
    - firm, cbsa, msa_name, emp_count, total_emp, emp_share, is_legacy
    
data/clean/firm_legacy_summary.csv
    - firm, total_emp_2019, n_legacy_locations, legacy_emp_share

Usage:
------
python py/build_firm_legacy_locations.py [--min-employees 100] [--min-share 0.10]
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

try:
    import duckdb
except ImportError:
    print("ERROR: DuckDB required. Install with: pip install duckdb")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROC = DATA / "processed"
RAW = DATA / "raw"

# Input
LINKEDIN_PANEL = PROC / "linkedin_panel.parquet"
MSA_ENRICHED = PROC / "enriched_msa.csv"

# Output
LEGACY_LOCATIONS = PROC / "firm_legacy_locations.csv"
LEGACY_SUMMARY = PROC / "firm_legacy_summary.csv"
QA_LOG = ROOT / "results" / "legacy_locations_qa.log"

# Constants
YH_2019H2 = 2019 * 2 + 1  # 4039

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
        "--min-employees", 
        type=int, 
        default=100,
        help="Minimum employees to qualify as legacy location"
    )
    parser.add_argument(
        "--min-share", 
        type=float, 
        default=0.05,
        help="Minimum share of firm employment to qualify as legacy (0.05 = 5%%)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed debugging output"
    )
    return parser.parse_args()


def build_legacy_locations(min_employees=100, min_share=0.05, debug=False):
    """
    Main pipeline to identify legacy office locations.
    """
    con = duckdb.connect()
    
    # Enable progress bar for long operations
    con.execute("SET enable_progress_bar = true;")
    
    print(f"\n{'='*70}")
    print(f"Building Legacy Office Locations")
    print(f"{'='*70}")
    print(f"Thresholds: {min_employees} employees OR {min_share:.1%} of firm")
    print(f"Using 2019-H2 (yh={YH_2019H2}) as baseline")
    
    # -----------------------------------------------------------------------
    # Step 1: Check input data
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 1: Checking input data...")
    
    if not LINKEDIN_PANEL.exists():
        print(f"ERROR: LinkedIn panel not found at {LINKEDIN_PANEL}")
        print("Run build_linkedin_panel_duckdb.py first")
        return False
    
    # Inspect the LinkedIn panel structure
    con.execute(f"""
        CREATE OR REPLACE VIEW linkedin AS
        SELECT * FROM parquet_scan('{LINKEDIN_PANEL}')
    """)
    
    # Check columns
    columns = con.execute("DESCRIBE linkedin").fetchall()
    col_names = [c[0] for c in columns]
    print(f"\nLinkedIn panel columns: {', '.join(col_names)}")
    
    required_cols = {'companyname', 'cbsa', 'yh', 'headcount'}
    missing = required_cols - set(col_names)
    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        return False
    
    # Check data availability for 2019-H2
    stats = con.execute(f"""
        SELECT 
            COUNT(DISTINCT companyname) as n_firms,
            COUNT(DISTINCT cbsa) as n_cbsas,
            SUM(headcount) as total_headcount
        FROM linkedin
        WHERE yh = {YH_2019H2}
    """).fetchone()
    
    print(f"\n2019-H2 data summary:")
    print(f"  - Firms: {stats[0]:,}")
    print(f"  - CBSAs: {stats[1]:,}")
    print(f"  - Total headcount: {stats[2]:,}")
    
    if stats[0] == 0:
        print("ERROR: No data found for 2019-H2")
        return False
    
    # -----------------------------------------------------------------------
    # Step 2: Calculate firm-MSA employment for 2019-H2
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 2: Calculating firm×MSA employment...")
    
    con.execute(f"""
        CREATE OR REPLACE TABLE firm_msa_2019 AS
        SELECT 
            LOWER(companyname) as firm,
            cbsa,
            SUM(headcount) as emp_count
        FROM linkedin
        WHERE yh = {YH_2019H2}
            AND companyname IS NOT NULL
            AND cbsa IS NOT NULL
        GROUP BY 1, 2
        HAVING emp_count > 0
    """)
    
    # Quality check
    sample = con.execute("""
        SELECT COUNT(*) as n_rows, 
               COUNT(DISTINCT firm) as n_firms,
               COUNT(DISTINCT cbsa) as n_cbsas,
               MIN(emp_count) as min_emp,
               MAX(emp_count) as max_emp
        FROM firm_msa_2019
    """).fetchone()
    
    print(f"\nFirm×MSA summary:")
    print(f"  - Rows: {sample[0]:,}")
    print(f"  - Unique firms: {sample[1]:,}")
    print(f"  - Unique CBSAs: {sample[2]:,}")
    print(f"  - Employment range: {sample[3]:,} to {sample[4]:,}")
    
    if debug:
        print("\nTop 10 firm-location combinations by employment:")
        top10 = con.execute("""
            SELECT firm, cbsa, emp_count
            FROM firm_msa_2019
            ORDER BY emp_count DESC
            LIMIT 10
        """).fetchall()
        for firm, cbsa, emp in top10:
            print(f"  {firm[:30]:30s} | CBSA {cbsa} | {emp:,} employees")
    
    # -----------------------------------------------------------------------
    # Step 3: Calculate firm totals
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 3: Calculating firm total employment...")
    
    con.execute("""
        CREATE OR REPLACE TABLE firm_totals AS
        SELECT 
            firm,
            SUM(emp_count) as total_emp,
            COUNT(DISTINCT cbsa) as n_locations
        FROM firm_msa_2019
        GROUP BY 1
    """)
    
    # Distribution check
    dist = con.execute("""
        SELECT 
            COUNT(*) as n_firms,
            MIN(total_emp) as min_emp,
            APPROX_QUANTILE(total_emp, 0.25) as q25,
            APPROX_QUANTILE(total_emp, 0.50) as median,
            APPROX_QUANTILE(total_emp, 0.75) as q75,
            MAX(total_emp) as max_emp,
            AVG(n_locations) as avg_locations
        FROM firm_totals
    """).fetchone()
    
    print(f"\nFirm size distribution:")
    print(f"  - Total firms: {dist[0]:,}")
    print(f"  - Employment: min={dist[1]:,}, Q25={dist[2]:,}, median={dist[3]:,}, Q75={dist[4]:,}, max={dist[5]:,}")
    print(f"  - Average locations per firm: {dist[6]:.1f}")
    
    # -----------------------------------------------------------------------
    # Step 4: Apply thresholds to identify legacy locations
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 4: Identifying legacy locations...")
    print(f"  Threshold 1: ≥ {min_employees} employees")
    print(f"  Threshold 2: ≥ {min_share:.1%} of firm employment")
    
    # Load MSA names for better readability
    if MSA_ENRICHED.exists():
        con.execute(f"""
            CREATE OR REPLACE TABLE msa_names AS
            SELECT 
                LPAD(CAST(cbsacode AS INTEGER)::VARCHAR, 5, '0') as cbsa,
                msa as msa_name
            FROM read_csv_auto('{MSA_ENRICHED}')
            WHERE cbsacode IS NOT NULL
        """)
        has_names = True
    else:
        print("  Warning: MSA names file not found, using CBSA codes only")
        has_names = False
    
    # Create the main legacy locations table
    con.execute(f"""
        CREATE OR REPLACE TABLE firm_legacy_locations AS
        SELECT 
            f.firm,
            f.cbsa,
            {('m.msa_name' if has_names else 'NULL as msa_name')},
            f.emp_count,
            t.total_emp,
            t.n_locations as firm_n_locations,
            ROUND(f.emp_count::FLOAT / t.total_emp, 4) as emp_share,
            CASE 
                WHEN f.emp_count >= {min_employees} THEN 1
                WHEN f.emp_count::FLOAT / t.total_emp >= {min_share} THEN 1
                ELSE 0
            END as is_legacy,
            CASE
                WHEN f.emp_count >= {min_employees} THEN 'min_employees'
                WHEN f.emp_count::FLOAT / t.total_emp >= {min_share} THEN 'min_share'
                ELSE NULL
            END as qualification_reason
        FROM firm_msa_2019 f
        JOIN firm_totals t ON f.firm = t.firm
        {('LEFT JOIN msa_names m ON f.cbsa = m.cbsa' if has_names else '')}
        ORDER BY f.firm, f.emp_count DESC
    """)
    
    # Summary statistics
    summary = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(*) as n_total_locations,
            SUM(is_legacy) as n_legacy_locations,
            COUNT(DISTINCT CASE WHEN is_legacy = 1 THEN firm END) as n_firms_with_legacy,
            AVG(CASE WHEN is_legacy = 1 THEN emp_share END) as avg_legacy_share
        FROM firm_legacy_locations
    """).fetchone()
    
    print(f"\nLegacy location summary:")
    print(f"  - Total firms: {summary[0]:,}")
    print(f"  - Total firm×location pairs: {summary[1]:,}")
    print(f"  - Legacy locations identified: {summary[2]:,}")
    print(f"  - Firms with ≥1 legacy location: {summary[3]:,}")
    print(f"  - Average employment share in legacy locations: {summary[4]:.1%}")
    
    # Check qualification reasons
    reasons = con.execute("""
        SELECT 
            qualification_reason,
            COUNT(*) as n_locations
        FROM firm_legacy_locations
        WHERE is_legacy = 1
        GROUP BY 1
    """).fetchall()
    
    print(f"\nQualification breakdown:")
    for reason, count in reasons:
        print(f"  - {reason}: {count:,} locations")
    
    # -----------------------------------------------------------------------
    # Step 5: Create firm-level summary
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 5: Creating firm-level summary...")
    
    con.execute("""
        CREATE OR REPLACE TABLE firm_legacy_summary AS
        SELECT 
            firm,
            MAX(total_emp) as total_emp_2019,
            MAX(firm_n_locations) as total_locations_2019,
            SUM(is_legacy) as n_legacy_locations,
            SUM(CASE WHEN is_legacy = 1 THEN emp_count ELSE 0 END) as legacy_emp_count,
            ROUND(SUM(CASE WHEN is_legacy = 1 THEN emp_count ELSE 0 END)::FLOAT / MAX(total_emp), 4) as legacy_emp_share,
            STRING_AGG(CASE WHEN is_legacy = 1 THEN cbsa END, '|' ORDER BY emp_count DESC) as legacy_cbsas
        FROM firm_legacy_locations
        GROUP BY 1
    """)
    
    # Distribution of legacy locations per firm
    dist = con.execute("""
        SELECT 
            n_legacy_locations,
            COUNT(*) as n_firms,
            AVG(total_emp_2019) as avg_firm_size
        FROM firm_legacy_summary
        GROUP BY 1
        ORDER BY 1
        LIMIT 15
    """).fetchall()
    
    print(f"\nDistribution of legacy locations per firm:")
    print(f"  {'Legacy Locs':>12} | {'# Firms':>8} | {'Avg Size':>10}")
    print(f"  {'-'*12} | {'-'*8} | {'-'*10}")
    for n_legacy, n_firms, avg_size in dist:
        print(f"  {n_legacy:>12} | {n_firms:>8,} | {avg_size:>10,.0f}")
    
    # -----------------------------------------------------------------------
    # Step 6: Quality checks
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 6: Running quality checks...")
    
    # Check for firms with no legacy locations
    no_legacy = con.execute("""
        SELECT COUNT(*) as n_firms, AVG(total_emp_2019) as avg_size
        FROM firm_legacy_summary
        WHERE n_legacy_locations = 0
    """).fetchone()
    
    if no_legacy[0] > 0:
        print(f"\n⚠️  Warning: {no_legacy[0]:,} firms have NO legacy locations")
        print(f"   (Average size: {no_legacy[1]:.0f} employees)")
        print(f"   These firms will have ALL post-2019 hires flagged as 'new geography'")
        
        if debug:
            print("\n   Examples of firms with no legacy locations:")
            examples = con.execute("""
                SELECT f.firm, f.total_emp_2019, f.total_locations_2019
                FROM firm_legacy_summary f
                WHERE n_legacy_locations = 0
                ORDER BY total_emp_2019 DESC
                LIMIT 5
            """).fetchall()
            for firm, emp, locs in examples:
                print(f"     {firm[:30]:30s} | {emp:,} employees | {locs} locations")
    
    # Check concentration
    concentration = con.execute("""
        WITH legacy_only AS (
            SELECT firm, cbsa, emp_count
            FROM firm_legacy_locations
            WHERE is_legacy = 1
        )
        SELECT 
            COUNT(DISTINCT cbsa) as unique_legacy_cbsas,
            COUNT(DISTINCT firm) as firms_with_legacy,
            AVG(emp_count) as avg_emp_per_legacy
        FROM legacy_only
    """).fetchone()
    
    print(f"\nLegacy location concentration:")
    print(f"  - Unique CBSAs marked as legacy: {concentration[0]:,}")
    print(f"  - Average employment per legacy location: {concentration[2]:,.0f}")
    
    # -----------------------------------------------------------------------
    # Step 7: Write outputs
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 7: Writing outputs...")
    
    # Write main legacy locations file
    con.execute(f"""
        COPY firm_legacy_locations 
        TO '{LEGACY_LOCATIONS}'
        WITH (HEADER, DELIMITER ',')
    """)
    print(f"  ✓ Wrote {LEGACY_LOCATIONS}")
    
    # Write summary file
    con.execute(f"""
        COPY firm_legacy_summary 
        TO '{LEGACY_SUMMARY}'
        WITH (HEADER, DELIMITER ',')
    """)
    print(f"  ✓ Wrote {LEGACY_SUMMARY}")
    
    # Write QA log
    QA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(QA_LOG, 'w') as f:
        f.write(f"Legacy Locations QA Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"{'='*70}\n\n")
        f.write(f"Parameters:\n")
        f.write(f"  - Min employees: {min_employees}\n")
        f.write(f"  - Min share: {min_share:.1%}\n")
        f.write(f"  - Year-half: {YH_2019H2} (2019-H2)\n\n")
        
        # Write key stats
        f.write(f"Summary Statistics:\n")
        f.write(f"  - Total firms: {summary[0]:,}\n")
        f.write(f"  - Total firm×location pairs: {summary[1]:,}\n")
        f.write(f"  - Legacy locations identified: {summary[2]:,}\n")
        f.write(f"  - Firms with ≥1 legacy location: {summary[3]:,}\n")
        f.write(f"  - Firms with NO legacy locations: {no_legacy[0]:,}\n")
        f.write(f"  - Unique CBSAs marked as legacy: {concentration[0]:,}\n\n")
        
        # Sample of large firms and their legacy locations
        f.write("Sample of largest firms and their legacy locations:\n")
        f.write("-" * 70 + "\n")
        samples = con.execute("""
            SELECT 
                s.firm,
                s.total_emp_2019,
                s.n_legacy_locations,
                s.legacy_emp_share,
                s.legacy_cbsas
            FROM firm_legacy_summary s
            ORDER BY s.total_emp_2019 DESC
            LIMIT 20
        """).fetchall()
        
        for firm, emp, n_legacy, share, cbsas in samples:
            f.write(f"{firm[:30]:30s} | {emp:6,} emp | {n_legacy:2} legacy | {share:5.1%} | ")
            if cbsas:
                f.write(f"CBSAs: {cbsas[:50]}")
            f.write("\n")
    
    print(f"  ✓ Wrote {QA_LOG}")
    
    print(f"\n{'='*70}")
    print("✅ Legacy location identification complete!")
    print(f"{'='*70}\n")
    
    con.close()
    return True


def main():
    """Main entry point."""
    args = parse_args()
    
    # Validate arguments
    if args.min_share < 0 or args.min_share > 1:
        print(f"ERROR: min_share must be between 0 and 1, got {args.min_share}")
        sys.exit(1)
    
    if args.min_employees < 0:
        print(f"ERROR: min_employees must be non-negative, got {args.min_employees}")
        sys.exit(1)
    
    success = build_legacy_locations(
        min_employees=args.min_employees,
        min_share=args.min_share,
        debug=args.debug
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()