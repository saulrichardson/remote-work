#!/usr/bin/env python3
"""
Build engineer vs non-engineer growth rates directly from the raw positions file.
"""

from __future__ import annotations

import argparse
import duckdb
from pathlib import Path


def build_growth(input_path: Path, output_path: Path, year_start: int, year_end: int) -> None:
    con = duckdb.connect(":memory:")
    query = f"""
    WITH positions AS (
        SELECT
            companyname,
            lower(companyname) AS companyname_c,
            user_id,
            role_k7,
            CAST(start_date AS DATE) AS start_dt,
            COALESCE(CAST(end_date AS DATE), DATE '{year_end}-12-31') AS end_dt
        FROM read_csv_auto('{input_path}', strict_mode=false, ignore_errors=true)
        WHERE companyname IS NOT NULL
          AND role_k7 IS NOT NULL
          AND start_date IS NOT NULL
    ),
    monthly AS (
        SELECT
            companyname,
            companyname_c,
            user_id,
            role_k7,
            DATE_TRUNC('month', period_dt) AS period_dt
        FROM (
            SELECT
                companyname,
                companyname_c,
                user_id,
                role_k7,
                UNNEST(
                    generate_series(
                        date_trunc('month', start_dt),
                        date_trunc('month', end_dt),
                        INTERVAL '1 month'
                    )
                ) AS period_dt
            FROM positions
        ) m
        WHERE EXTRACT(year FROM period_dt) BETWEEN {year_start} AND {year_end}
    ),
    counts AS (
        SELECT
            companyname,
            companyname_c,
            role_k7,
            CAST(EXTRACT(year FROM period_dt) AS INT) AS year,
            CAST(CASE WHEN EXTRACT(month FROM period_dt) <= 6 THEN 1 ELSE 2 END AS INT) AS half,
            COUNT(DISTINCT user_id) AS employee_count
        FROM monthly
        GROUP BY 1,2,3,4,5
    ),
    engineer AS (
        SELECT
            companyname,
            companyname_c,
            year,
            half,
            employee_count AS emp_eng,
            LAG(employee_count) OVER (
                PARTITION BY companyname, companyname_c
                ORDER BY year, half
            ) AS prev_emp_eng
        FROM counts
        WHERE role_k7 = 'Engineer'
    ),
    nonengineer AS (
        SELECT
            companyname,
            companyname_c,
            year,
            half,
            SUM(employee_count) AS emp_noneng
        FROM counts
        WHERE role_k7 <> 'Engineer'
        GROUP BY 1,2,3,4
    ),
    nonengineer_lag AS (
        SELECT
            companyname,
            companyname_c,
            year,
            half,
            emp_noneng,
            LAG(emp_noneng) OVER (
                PARTITION BY companyname, companyname_c
                ORDER BY year, half
            ) AS prev_emp_noneng
        FROM nonengineer
    )
    SELECT
        COALESCE(e.companyname, n.companyname) AS companyname,
        COALESCE(e.companyname_c, n.companyname_c) AS companyname_c,
        COALESCE(e.year, n.year) AS year,
        COALESCE(e.half, n.half) AS half,
        (COALESCE(e.year, n.year) * 10 + COALESCE(e.half, n.half)) AS yh,
        CASE
            WHEN e.prev_emp_eng > 0 THEN (e.emp_eng - e.prev_emp_eng) / e.prev_emp_eng
            ELSE NULL
        END AS pct_growth_eng,
        CASE
            WHEN n.prev_emp_noneng > 0 THEN (n.emp_noneng - n.prev_emp_noneng) / n.prev_emp_noneng
            ELSE NULL
        END AS pct_growth_noneng
    FROM engineer e
    FULL OUTER JOIN nonengineer_lag n
      ON e.companyname_c = n.companyname_c
     AND e.year = n.year
     AND e.half = n.half
    ORDER BY companyname, year, half
    """
    df = con.execute(query).df()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build engineer vs non-engineer growth inputs.")
    parser.add_argument("--input", required=True, help="Path to Scoop_workers_positions.csv")
    parser.add_argument("--output", required=True, help="Destination CSV path")
    parser.add_argument("--year-start", type=int, default=2015, help="Earliest year to include")
    parser.add_argument("--year-end", type=int, default=2023, help="Latest year to include")
    args = parser.parse_args()

    build_growth(Path(args.input), Path(args.output), args.year_start, args.year_end)


if __name__ == "__main__":
    main()
