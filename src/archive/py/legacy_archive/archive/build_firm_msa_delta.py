#!/usr/bin/env python3
"""
Build firm-level ex-post CBSA breadth changes (Δ) and expansion flags.

Uses data/clean/linkedin_panel.parquet with columns:
  - companyname, cbsa, yh, headcount, joins

Outputs:
  data/clean/firm_msa_delta.csv with columns:
    companyname_lower,
    pre_avg_hc5r1, post_avg_hc5r1, delta_hc5r1, exp_hc5r1,
    pre_avg_hc10r2, post_avg_hc10r2, delta_hc10r2, exp_hc10r2,
    pre_avg_join3r3, post_avg_join3r3, delta_join3r3,
    lastpre_hc0, firstpost_hc0, delta_jump_hc0

Definitions (per firm×half-year):
  - hc5r1: count of distinct CBSAs with headcount ≥ 5 and share ≥ 1%
  - hc10r2: count of distinct CBSAs with headcount ≥ 10 and share ≥ 2%
  - join3r3: count of distinct CBSAs with joins ≥ 3 and share ≥ 3%
  - hc0 (for immediate jump diagnostic): CBSAs with headcount > 0

Pre period: yh ≤ 4039 (through 2019-H2)
Post period: yh ≥ 4040 (2020-H1 onwards)
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
PANEL = PROC / "linkedin_panel.parquet"
OUT = PROC / "firm_msa_delta.csv"
QA = ROOT / "results" / "firm_msa_delta_qa.log"


def main() -> int:
    if not PANEL.exists():
        print(f"ERROR: Missing input parquet: {PANEL}")
        return 1

    con = duckdb.connect()
    con.execute("SET enable_progress_bar = true;")

    con.execute(
        f"""
        CREATE OR REPLACE VIEW li AS
        SELECT LOWER(companyname) AS firm, cbsa, yh,
               COALESCE(headcount,0) AS headcount,
               COALESCE(joins,0)     AS joins
        FROM parquet_scan('{PANEL.as_posix()}')
        WHERE companyname IS NOT NULL AND cbsa IS NOT NULL
        """
    )

    # Build breadth measures per firm×yh under multiple filters
    con.execute(
        """
        CREATE OR REPLACE TABLE breadth AS
        WITH denom AS (
            SELECT firm, yh,
                   SUM(headcount) AS hc_tot,
                   SUM(joins)     AS j_tot
            FROM li
            GROUP BY 1,2
        )
        SELECT l.firm, l.yh,
               COUNT(DISTINCT CASE WHEN l.headcount > 0 THEN cbsa END) AS hc0,
               COUNT(DISTINCT CASE WHEN l.headcount >= 5  AND l.headcount/NULLIF(d.hc_tot,0) >= 0.01 THEN cbsa END) AS hc5r1,
               COUNT(DISTINCT CASE WHEN l.headcount >= 10 AND l.headcount/NULLIF(d.hc_tot,0) >= 0.02 THEN cbsa END) AS hc10r2,
               COUNT(DISTINCT CASE WHEN l.joins >= 3     AND l.joins/NULLIF(d.j_tot,0)       >= 0.03 THEN cbsa END) AS join3r3
        FROM li l
        JOIN denom d USING (firm, yh)
        GROUP BY 1,2
        ORDER BY 1,2
        """
    )

    # Aggregate to pre/post averages and compute deltas
    con.execute(
        """
        CREATE OR REPLACE TABLE firm_delta AS
        WITH pre AS (
            SELECT firm,
                   AVG(hc5r1)   AS pre_avg_hc5r1,
                   AVG(hc10r2)  AS pre_avg_hc10r2,
                   AVG(join3r3) AS pre_avg_join3r3
            FROM breadth WHERE yh <= 4039 GROUP BY firm
        ), post AS (
            SELECT firm,
                   AVG(hc5r1)   AS post_avg_hc5r1,
                   AVG(hc10r2)  AS post_avg_hc10r2,
                   AVG(join3r3) AS post_avg_join3r3
            FROM breadth WHERE yh >= 4040 GROUP BY firm
        ), jump AS (
            SELECT p.firm,
                   p.hc0 AS lastpre_hc0,
                   f.hc0 AS firstpost_hc0,
                   (f.hc0 - p.hc0) AS delta_jump_hc0
            FROM (
                SELECT b.firm, b.hc0
                FROM breadth b
                JOIN (
                    SELECT firm, MAX(yh) AS yh FROM breadth WHERE yh<=4039 GROUP BY firm
                ) m USING (firm, yh)
            ) p
            JOIN (
                SELECT b.firm, b.hc0
                FROM breadth b
                JOIN (
                    SELECT firm, MIN(yh) AS yh FROM breadth WHERE yh>=4040 GROUP BY firm
                ) m USING (firm, yh)
            ) f USING (firm)
        )
        SELECT p.firm AS companyname_lower,
               p.pre_avg_hc5r1,  o.post_avg_hc5r1,  (o.post_avg_hc5r1  - p.pre_avg_hc5r1)  AS delta_hc5r1,
               CASE WHEN (o.post_avg_hc5r1 - p.pre_avg_hc5r1) > 0 THEN 1 ELSE 0 END        AS exp_hc5r1,
               p.pre_avg_hc10r2, o.post_avg_hc10r2, (o.post_avg_hc10r2 - p.pre_avg_hc10r2) AS delta_hc10r2,
               CASE WHEN (o.post_avg_hc10r2 - p.pre_avg_hc10r2) > 0 THEN 1 ELSE 0 END       AS exp_hc10r2,
               p.pre_avg_join3r3, o.post_avg_join3r3, (o.post_avg_join3r3 - p.pre_avg_join3r3) AS delta_join3r3,
               j.lastpre_hc0, j.firstpost_hc0, j.delta_jump_hc0
        FROM pre p
        JOIN post o ON o.firm = p.firm
        LEFT JOIN jump j ON j.firm = p.firm
        ORDER BY 1
        """
    )

    # Write outputs
    con.execute(f"COPY firm_delta TO '{OUT.as_posix()}' WITH (HEADER, DELIMITER ',')")

    # QA log
    QA.parent.mkdir(parents=True, exist_ok=True)
    n, ppos = con.execute(
        """
        SELECT COUNT(*), AVG(CASE WHEN delta_hc5r1>0 THEN 1.0 ELSE 0.0 END)
        FROM firm_delta
        """
    ).fetchone()
    with open(QA, "w") as f:
        f.write("Firm Δ CBSA breadth QA\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("="*70 + "\n")
        f.write(f"Rows (firms): {n}\n")
        f.write(f"Share exp_hc5r1 (Δ>0): {ppos:.3f}\n")

    print(f"✓ Wrote {OUT}")
    print(f"✓ Wrote {QA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

