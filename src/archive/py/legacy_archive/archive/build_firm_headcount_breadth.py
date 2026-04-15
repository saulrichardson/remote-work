#!/usr/bin/env python3
"""
Build time-varying headcount-based geographic breadth by firm×half-year.

Output:
  data/clean/firm_headcount_breadth.csv
  - companyname_lower, yh, n_cbsa_headcount

Source:
  data/clean/linkedin_panel.parquet
  Expected columns: companyname, cbsa, yh, headcount
"""

from pathlib import Path
from datetime import datetime
import sys

try:
    import duckdb
except ImportError:
    print("ERROR: DuckDB required. Install with: pip install duckdb")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PROC = DATA / "processed"

LINKEDIN_PANEL = PROC / "linkedin_panel.parquet"
OUT_CSV = PROC / "firm_headcount_breadth.csv"
QA_LOG = ROOT / "results" / "headcount_breadth_qa.log"


def main() -> int:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = true;")

    if not LINKEDIN_PANEL.exists():
        print(f"ERROR: Missing input: {LINKEDIN_PANEL}")
        return 1

    # Create a view over the parquet
    con.execute(f"""
        CREATE OR REPLACE VIEW linkedin AS
        SELECT * FROM parquet_scan('{LINKEDIN_PANEL}')
    """)

    # Basic schema check
    cols = {r[0] for r in con.execute("DESCRIBE linkedin").fetchall()}
    required = {"companyname", "cbsa", "yh", "headcount"}
    missing = required - cols
    if missing:
        print(f"ERROR: Missing required columns in linkedin_panel: {missing}")
        return 1

    # Build time-varying breadth (distinct CBSAs with positive headcount)
    con.execute(
        """
        CREATE OR REPLACE TABLE firm_breadth AS
        SELECT
            LOWER(companyname) AS companyname_lower,
            yh,
            COUNT(DISTINCT CASE WHEN headcount > 0 AND cbsa IS NOT NULL THEN cbsa END) AS n_cbsa_headcount
        FROM linkedin
        WHERE companyname IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    )

    # Quick stats
    nrows, nfirms, nperiods, avg_breadth = con.execute(
        """
        SELECT COUNT(*) , COUNT(DISTINCT companyname_lower), COUNT(DISTINCT yh), AVG(n_cbsa_headcount)
        FROM firm_breadth
        """
    ).fetchone()

    # Write output
    con.execute(
        f"""
        COPY firm_breadth TO '{OUT_CSV}' WITH (HEADER, DELIMITER ',')
        """
    )

    # QA log
    QA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(QA_LOG, "w") as f:
        f.write("Headcount Breadth QA Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Rows: {nrows:,}\n")
        f.write(f"Firms: {nfirms:,}\n")
        f.write(f"Periods: {nperiods:,}\n")
        f.write(f"Average breadth: {avg_breadth:.2f}\n")

    print(f"✓ Wrote {OUT_CSV}")
    print(f"✓ Wrote {QA_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

