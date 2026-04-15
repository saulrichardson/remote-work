#!/usr/bin/env python3
"""
Build each firm's set of "legacy office locations" using RAW LinkedIn data.

This version reads directly from the 10GB Scoop_workers_positions.csv to get
accurate employee counts per location as of 2019-12-31.

A location qualifies as a legacy office if it meets EITHER:
- Has ≥ min_employees (default: 100)
- Has ≥ min_share of firm employment (default: 0.10 = 10%)

Outputs:
--------
data/clean/firm_legacy_locations_raw.csv
    - firm, cbsa, msa_name, emp_count, total_emp, emp_share, is_legacy
    
data/clean/firm_legacy_summary_raw.csv
    - firm, total_emp_2019, n_legacy_locations, legacy_emp_share

Usage:
------
python py/build_firm_legacy_locations_raw.py [--min-employees 100] [--min-share 0.10]
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

# Input - using the RAW LinkedIn file
LINKEDIN_RAW = RAW / "Scoop_workers_positions.csv"
MSA_ENRICHED = PROC / "enriched_msa.csv"

# Output
LEGACY_LOCATIONS = PROC / "firm_legacy_locations_raw.csv"
LEGACY_SUMMARY = PROC / "firm_legacy_summary_raw.csv"
QA_LOG = ROOT / "results" / "legacy_locations_raw_qa.log"

# Reference date
CUTOFF_DATE = '2019-12-31'

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
        default=0.10,
        help="Minimum share of firm employment to qualify as legacy (0.10 = 10%%)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed debugging output"
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Process only first N rows for testing"
    )
    return parser.parse_args()


def build_legacy_locations(min_employees=100, min_share=0.10, debug=False, sample=None):
    """
    Main pipeline to identify legacy office locations from raw data.
    """
    con = duckdb.connect()
    
    # Configure DuckDB for large dataset
    con.execute("SET memory_limit = '8GB';")
    con.execute("SET threads = 8;")
    con.execute("SET enable_progress_bar = true;")
    
    print(f"\n{'='*70}")
    print(f"Building Legacy Office Locations from RAW LinkedIn Data")
    print(f"{'='*70}")
    print(f"Thresholds: {min_employees} employees OR {min_share:.1%} of firm")
    print(f"Using snapshot date: {CUTOFF_DATE}")
    
    # -----------------------------------------------------------------------
    # Step 1: Check input data
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 1: Checking input data...")
    
    if not LINKEDIN_RAW.exists():
        print(f"ERROR: Raw LinkedIn file not found at {LINKEDIN_RAW}")
        return False
    
    # Check file size
    file_size_gb = LINKEDIN_RAW.stat().st_size / (1024**3)
    print(f"\nRaw LinkedIn file size: {file_size_gb:.1f} GB")
    
    # Sample the file to check structure
    sample_clause = f"LIMIT {sample}" if sample else ""
    
    print("\nChecking file structure...")
    con.execute(f"""
        CREATE OR REPLACE VIEW linkedin_sample AS
        SELECT * FROM read_csv_auto('{LINKEDIN_RAW}', 
            sample_size=1000,
            all_varchar=true)
        {sample_clause}
    """)
    
    # Check columns
    columns = con.execute("DESCRIBE linkedin_sample").fetchall()
    col_names = [c[0] for c in columns]
    print(f"Columns found: {', '.join(col_names[:10])}...")
    
    # -----------------------------------------------------------------------
    # Step 2: Load and filter to 2019-12-31 snapshot
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 2: Loading 2019-12-31 employment snapshot...")
    print("This may take several minutes for the 10GB file...")
    
    # First, let's check what date columns we have
    date_cols = [c for c in col_names if 'date' in c.lower()]
    print(f"Date columns found: {date_cols}")
    
    # Create the filtered view
    # We need employees who were active on 2019-12-31
    # Use ignore_errors to handle CSV parsing issues
    con.execute(f"""
        CREATE OR REPLACE TABLE employees_2019 AS
        SELECT 
            LOWER(companyname) as firm,
            msa,
            user_id
        FROM read_csv('{LINKEDIN_RAW}', 
            AUTO_DETECT=true,
            ignore_errors=true,
            all_varchar=true,
            parallel=true) 
        WHERE companyname IS NOT NULL
            AND msa IS NOT NULL
            AND msa != ''
            AND msa != 'empty'
            AND msa NOT LIKE '%empty%'
            AND start_date IS NOT NULL
            AND start_date != ''
            AND start_date <= '{CUTOFF_DATE}'
            AND (end_date IS NULL OR end_date = '' OR end_date >= '{CUTOFF_DATE}')
        {sample_clause}
    """)
    
    # Get counts
    stats = con.execute("""
        SELECT 
            COUNT(*) as n_records,
            COUNT(DISTINCT firm) as n_firms,
            COUNT(DISTINCT msa) as n_msas,
            COUNT(DISTINCT user_id) as n_employees
        FROM employees_2019
    """).fetchone()
    
    print(f"\n2019-12-31 snapshot loaded:")
    print(f"  - Records: {stats[0]:,}")
    print(f"  - Firms: {stats[1]:,}")
    print(f"  - MSAs: {stats[2]:,}")
    print(f"  - Unique employees: {stats[3]:,}")
    
    if stats[1] == 0:
        print("ERROR: No data found for 2019-12-31")
        return False
    
    # -----------------------------------------------------------------------
    # Step 3: Map MSA names to CBSA codes
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 3: Mapping MSA names to CBSA codes...")
    
    if MSA_ENRICHED.exists():
        con.execute(f"""
            CREATE OR REPLACE TABLE msa_map AS
            SELECT 
                LOWER(TRIM(msa)) as msa_name,
                LPAD(CAST(cbsacode AS INTEGER)::VARCHAR, 5, '0') as cbsa,
                msa as msa_display
            FROM read_csv_auto('{MSA_ENRICHED}')
            WHERE cbsacode IS NOT NULL
        """)
        
        # Try to match
        con.execute("""
            CREATE OR REPLACE TABLE employees_2019_cbsa AS
            SELECT 
                e.firm,
                COALESCE(m.cbsa, 'UNMAPPED_' || e.msa) as cbsa,
                COALESCE(m.msa_display, e.msa) as msa_name,
                e.user_id
            FROM employees_2019 e
            LEFT JOIN msa_map m ON LOWER(TRIM(e.msa)) = m.msa_name
        """)
    else:
        print("  Warning: MSA enrichment file not found, using MSA names as-is")
        con.execute("""
            CREATE OR REPLACE TABLE employees_2019_cbsa AS
            SELECT 
                firm,
                msa as cbsa,
                msa as msa_name,
                user_id
            FROM employees_2019
        """)
    
    # Check mapping success
    unmapped = con.execute("""
        SELECT COUNT(DISTINCT cbsa) as n_unmapped
        FROM employees_2019_cbsa
        WHERE cbsa LIKE 'UNMAPPED_%'
    """).fetchone()[0]
    
    if unmapped > 0:
        print(f"  Warning: {unmapped} MSAs could not be mapped to CBSA codes")
    
    # -----------------------------------------------------------------------
    # Step 4: Calculate firm-location employment
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 4: Calculating firm×location employment...")
    
    con.execute("""
        CREATE OR REPLACE TABLE firm_location_2019 AS
        SELECT 
            firm,
            cbsa,
            MAX(msa_name) as msa_name,
            COUNT(DISTINCT user_id) as emp_count
        FROM employees_2019_cbsa
        GROUP BY firm, cbsa
        HAVING emp_count > 0
    """)
    
    # Summary
    summary = con.execute("""
        SELECT 
            COUNT(*) as n_rows,
            COUNT(DISTINCT firm) as n_firms,
            COUNT(DISTINCT cbsa) as n_locations,
            MIN(emp_count) as min_emp,
            MAX(emp_count) as max_emp,
            AVG(emp_count) as avg_emp
        FROM firm_location_2019
    """).fetchone()
    
    print(f"\nFirm×location summary:")
    print(f"  - Firm-location pairs: {summary[0]:,}")
    print(f"  - Unique firms: {summary[1]:,}")
    print(f"  - Unique locations: {summary[2]:,}")
    print(f"  - Employment range: {summary[3]:,} to {summary[4]:,}")
    print(f"  - Average employment: {summary[5]:.1f}")
    
    if debug:
        print("\nTop 10 firm-location combinations:")
        top10 = con.execute("""
            SELECT firm, msa_name, cbsa, emp_count
            FROM firm_location_2019
            ORDER BY emp_count DESC
            LIMIT 10
        """).fetchall()
        for firm, msa, cbsa, emp in top10:
            print(f"  {firm[:25]:25s} | {msa[:30]:30s} | {emp:,} employees")
    
    # -----------------------------------------------------------------------
    # Step 5: Calculate firm totals
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 5: Calculating firm totals...")
    
    con.execute("""
        CREATE OR REPLACE TABLE firm_totals AS
        SELECT 
            firm,
            SUM(emp_count) as total_emp,
            COUNT(DISTINCT cbsa) as n_locations
        FROM firm_location_2019
        GROUP BY firm
    """)
    
    # Size distribution
    dist = con.execute("""
        SELECT 
            COUNT(*) as n_firms,
            MIN(total_emp) as min_emp,
            APPROX_QUANTILE(total_emp, 0.25) as q25,
            APPROX_QUANTILE(total_emp, 0.50) as median,
            APPROX_QUANTILE(total_emp, 0.75) as q75,
            MAX(total_emp) as max_emp
        FROM firm_totals
    """).fetchone()
    
    print(f"\nFirm size distribution:")
    print(f"  - Total firms: {dist[0]:,}")
    print(f"  - Min: {dist[1]:,}, Q25: {dist[2]:,}, Median: {dist[3]:,}")
    print(f"  - Q75: {dist[4]:,}, Max: {dist[5]:,}")
    
    # -----------------------------------------------------------------------
    # Step 6: Apply thresholds to identify legacy locations
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 6: Identifying legacy locations...")
    print(f"  Threshold 1: ≥ {min_employees} employees")
    print(f"  Threshold 2: ≥ {min_share:.1%} of firm employment")
    
    con.execute(f"""
        CREATE OR REPLACE TABLE firm_legacy_locations_raw AS
        SELECT 
            f.firm,
            f.cbsa,
            f.msa_name,
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
        FROM firm_location_2019 f
        JOIN firm_totals t ON f.firm = t.firm
        ORDER BY f.firm, f.emp_count DESC
    """)
    
    # Summary
    legacy_stats = con.execute("""
        SELECT 
            COUNT(DISTINCT firm) as n_firms,
            COUNT(*) as n_total_locations,
            SUM(is_legacy) as n_legacy_locations,
            COUNT(DISTINCT CASE WHEN is_legacy = 1 THEN firm END) as n_firms_with_legacy,
            AVG(CASE WHEN is_legacy = 1 THEN emp_share END) as avg_legacy_share
        FROM firm_legacy_locations_raw
    """).fetchone()
    
    print(f"\nLegacy location results:")
    print(f"  - Total firms: {legacy_stats[0]:,}")
    print(f"  - Total firm×location pairs: {legacy_stats[1]:,}")
    print(f"  - Legacy locations identified: {legacy_stats[2]:,}")
    print(f"  - Firms with ≥1 legacy location: {legacy_stats[3]:,}")
    if legacy_stats[4]:
        print(f"  - Average employment share in legacy locations: {legacy_stats[4]:.1%}")
    
    # Qualification breakdown
    qual = con.execute("""
        SELECT 
            qualification_reason,
            COUNT(*) as n_locations,
            AVG(emp_count) as avg_emp
        FROM firm_legacy_locations_raw
        WHERE is_legacy = 1
        GROUP BY qualification_reason
    """).fetchall()
    
    print(f"\nQualification breakdown:")
    for reason, count, avg_emp in qual:
        print(f"  - {reason}: {count:,} locations (avg: {avg_emp:.0f} employees)")
    
    # -----------------------------------------------------------------------
    # Step 7: Create firm summary
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 7: Creating firm-level summary...")
    
    con.execute("""
        CREATE OR REPLACE TABLE firm_legacy_summary_raw AS
        SELECT 
            firm,
            MAX(total_emp) as total_emp_2019,
            MAX(firm_n_locations) as total_locations_2019,
            SUM(is_legacy) as n_legacy_locations,
            SUM(CASE WHEN is_legacy = 1 THEN emp_count ELSE 0 END) as legacy_emp_count,
            ROUND(
                SUM(CASE WHEN is_legacy = 1 THEN emp_count ELSE 0 END)::FLOAT / MAX(total_emp), 
                4
            ) as legacy_emp_share,
            STRING_AGG(
                CASE WHEN is_legacy = 1 THEN cbsa || ':' || msa_name END, 
                '|' 
                ORDER BY emp_count DESC
            ) as legacy_locations
        FROM firm_legacy_locations_raw
        GROUP BY firm
    """)
    
    # Check firms with no legacy
    no_legacy = con.execute("""
        SELECT COUNT(*) as n_firms, AVG(total_emp_2019) as avg_size
        FROM firm_legacy_summary_raw
        WHERE n_legacy_locations = 0
    """).fetchone()
    
    if no_legacy[0] > 0:
        print(f"\n⚠️  Warning: {no_legacy[0]:,} firms have NO legacy locations")
        print(f"   Average size: {no_legacy[1]:.0f} employees")
    
    # -----------------------------------------------------------------------
    # Step 8: Write outputs
    # -----------------------------------------------------------------------
    print(f"\n{'─'*50}")
    print("Step 8: Writing output files...")
    
    # Main locations file
    con.execute(f"""
        COPY firm_legacy_locations_raw
        TO '{LEGACY_LOCATIONS}'
        WITH (HEADER, DELIMITER ',')
    """)
    print(f"  ✓ {LEGACY_LOCATIONS}")
    
    # Summary file
    con.execute(f"""
        COPY firm_legacy_summary_raw
        TO '{LEGACY_SUMMARY}'
        WITH (HEADER, DELIMITER ',')
    """)
    print(f"  ✓ {LEGACY_SUMMARY}")
    
    # QA log
    QA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(QA_LOG, 'w') as f:
        f.write(f"Legacy Locations QA Report (from RAW data)\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"{'='*70}\n\n")
        f.write(f"Input file: {LINKEDIN_RAW} ({file_size_gb:.1f} GB)\n")
        f.write(f"Snapshot date: {CUTOFF_DATE}\n\n")
        f.write(f"Parameters:\n")
        f.write(f"  - Min employees: {min_employees}\n")
        f.write(f"  - Min share: {min_share:.1%}\n\n")
        
        if sample:
            f.write(f"⚠️  SAMPLE MODE: Only processed first {sample:,} rows\n\n")
        
        f.write(f"Results:\n")
        f.write(f"  - Firms analyzed: {legacy_stats[0]:,}\n")
        f.write(f"  - Legacy locations: {legacy_stats[2]:,}\n")
        f.write(f"  - Firms with no legacy: {no_legacy[0]:,}\n")
    
    print(f"  ✓ {QA_LOG}")
    
    print(f"\n{'='*70}")
    print("✅ Legacy location identification complete!")
    print(f"{'='*70}\n")
    
    con.close()
    return True


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.min_share < 0 or args.min_share > 1:
        print(f"ERROR: min_share must be between 0 and 1")
        sys.exit(1)
    
    success = build_legacy_locations(
        min_employees=args.min_employees,
        min_share=args.min_share,
        debug=args.debug,
        sample=args.sample
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()