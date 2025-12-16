#!/usr/bin/env python3
"""
Build a user-level wage panel directly from the LinkedIn spell dump using DuckDB.

The script:
1. Loads the raw `Scoop_workers_positions.csv` file.
2. Expands each spell to half-year observations.
3. Merges firm-level controls (teleworkable score, flexibility/remote metrics,
   founding year).
4. Computes the interaction variables expected by `spec/user_wage.do`.
5. Writes a compact CSV/Parquet that Stata can ingest without the productivity
   panel pipeline.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd
import pyreadstat

from project_paths import DATA_CLEAN, DATA_RAW

DEFAULT_OUTPUT = DATA_CLEAN / "user_wage_panel_full.parquet"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("Build user wage panel via DuckDB")
    p.add_argument("--spells", default=str(DATA_RAW / "Scoop_workers_positions.csv"),
                   help="Raw LinkedIn spell CSV")
    p.add_argument("--teleworkable", default=str(DATA_CLEAN / "scoop_firm_tele_2.dta"),
                   help="Firm-level teleworkable scores (Stata DTA)")
    p.add_argument("--remote", default=str(DATA_RAW / "Scoop_clean_public.dta"),
                   help="Firm-level flexibility/remote metrics (Stata DTA)")
    p.add_argument("--founding", default=str(DATA_RAW / "Scoop_founding.dta"),
                   help="Firm founding year (Stata DTA)")
    p.add_argument("--output", default=str(DEFAULT_OUTPUT),
                   help="Destination file (extension determines format)")
    p.add_argument("--sample", type=int,
                   help="Limit number of rows read from the spell CSV (debug)")
    p.add_argument("--threads", type=int,
                   help="DuckDB worker threads (default: DuckDB decides)")
    p.add_argument("--temp-dir",
                   help="Directory for DuckDB temp storage (PRAGMA temp_directory)")
    return p.parse_args()


def _load_dta(path: str | Path, columns: Iterable[str]) -> pd.DataFrame:
    df, _ = pyreadstat.read_dta(str(path), usecols=list(columns))
    return df


def _standardise_company(df: pd.DataFrame, column: str = "companyname") -> pd.DataFrame:
    out = df.copy()
    out["companyname_c"] = out[column].str.strip().str.lower()
    out = out.dropna(subset=["companyname_c"])
    return out


def main() -> None:  # noqa: C901
    ns = _parse_args()

    out_path = Path(ns.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output_format = out_path.suffix.lower().lstrip(".") or "parquet"

    con = duckdb.connect()

    if ns.threads:
        con.execute(f"PRAGMA threads={ns.threads};")

    temp_dir = ns.temp_dir or os.environ.get("DUCKDB_TEMP_DIRECTORY")
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        safe_dir = temp_dir.replace("'", "''")
        con.execute(f"PRAGMA temp_directory='{safe_dir}';")

    limit_clause = f"LIMIT {ns.sample}" if ns.sample else ""

    # 1) Raw spells → table
    con.execute(
        f"""
        CREATE OR REPLACE TABLE spells AS
        SELECT
            CAST(user_id AS BIGINT)                                         AS user_id,
            LOWER(TRIM(companyname))                                        AS companyname_c,
            companyname                                                     AS companyname,
            title                                                           AS title,
            CAST(position_id AS BIGINT)                                     AS position_id,
            role_k1000,
            CAST(salary AS DOUBLE)                                          AS salary,
            CAST(start_date AS DATE)                                        AS start_date,
            COALESCE(CAST(end_date AS DATE), CAST(start_date AS DATE))      AS end_date
        FROM read_csv_auto(
            '{ns.spells}',
            ignore_errors=true,
            SAMPLE_SIZE=2000000,
            strict_mode=false
        )
        {limit_clause};
        """
    )

    con.execute("DELETE FROM spells WHERE salary IS NULL OR salary <= 0 OR start_date IS NULL;")

    # 2) Expand to half-year observations
    con.execute(
        """
        CREATE OR REPLACE TABLE spells_half AS
        WITH bounds AS (
            SELECT
                *,
                CASE
                    WHEN EXTRACT(month FROM start_date) <= 6
                        THEN DATE_TRUNC('year', start_date)
                    ELSE DATE_TRUNC('year', start_date) + INTERVAL '6 months'
                END AS first_half,
                CASE
                    WHEN EXTRACT(month FROM end_date) <= 6
                        THEN DATE_TRUNC('year', end_date)
                    ELSE DATE_TRUNC('year', end_date) + INTERVAL '6 months'
                END AS last_half
            FROM spells
        )
        SELECT
            b.user_id,
            b.companyname,
            b.companyname_c,
            b.position_id,
            b.title,
            b.role_k1000,
            b.salary,
            b.start_date,
            b.end_date,
            gs.half_start                                       AS yh_date,
            EXTRACT(year FROM gs.half_start)::INT               AS year,
            CASE WHEN EXTRACT(month FROM gs.half_start) = 1 THEN 1 ELSE 2 END AS half
        FROM bounds b,
        LATERAL generate_series(first_half, last_half, INTERVAL '6 months') AS gs(half_start);
        """
    )

    # Deduplicate to one row per user × half-year (keep latest spell)
    con.execute(
        """
        CREATE OR REPLACE TABLE panel_base AS
        SELECT *
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, year, half
                    ORDER BY end_date DESC NULLS LAST,
                             start_date DESC NULLS LAST,
                             salary DESC NULLS LAST,
                             position_id DESC NULLS LAST
                ) AS rn
            FROM spells_half
        )
        WHERE rn = 1;
        """
    )

    con.execute("ALTER TABLE panel_base DROP COLUMN rn;")

    # 3) Load firm-level controls (pandas → DuckDB)
    tele_df = _standardise_company(_load_dta(ns.teleworkable, ["companyname", "teleworkable"]))
    remote_df = _standardise_company(_load_dta(ns.remote, ["companyname", "flexibility_score2"]))
    founding_df = _standardise_company(_load_dta(ns.founding, ["companyname", "founded"]))

    con.register("tele_df", tele_df)
    con.register("remote_df", remote_df)
    con.register("founding_df", founding_df)

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE tele_clean AS
        SELECT companyname_c, teleworkable
        FROM tele_df
        WHERE teleworkable IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY companyname_c ORDER BY companyname_c) = 1;
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE remote_clean AS
        SELECT companyname_c, flexibility_score2
        FROM remote_df
        WHERE flexibility_score2 IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY companyname_c ORDER BY companyname_c) = 1;
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE founding_clean AS
        SELECT companyname_c, founded
        FROM founding_df
        WHERE founded IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY companyname_c ORDER BY companyname_c) = 1;
        """
    )

    # 4) Build the wage-ready panel with interactions
    con.execute(
        """
        CREATE OR REPLACE TABLE user_wage_panel AS
        SELECT
            s.user_id,
            s.companyname,
            s.companyname_c,
            s.title,
            s.yh_date,
            s.year,
            s.half,
            s.salary,
            LN(s.salary)                                               AS log_salary,
            r.flexibility_score2                                       AS remote,
            (2020 - f.founded)                                         AS age,
            CASE WHEN (2020 - f.founded) <= 10 THEN 1 ELSE 0 END       AS startup,
            CASE WHEN s.year >= 2020 THEN 1 ELSE 0 END                 AS covid,
            t.teleworkable,
            (r.flexibility_score2 * CASE WHEN s.year >= 2020 THEN 1 ELSE 0 END)                 AS var3,
            (CASE WHEN s.year >= 2020 THEN 1 ELSE 0 END * CASE WHEN (2020 - f.founded) <= 10 THEN 1 ELSE 0 END) AS var4,
            (r.flexibility_score2 * CASE WHEN s.year >= 2020 THEN 1 ELSE 0 END * CASE WHEN (2020 - f.founded) <= 10 THEN 1 ELSE 0 END) AS var5,
            (CASE WHEN s.year >= 2020 THEN 1 ELSE 0 END * t.teleworkable)                      AS var6,
            (CASE WHEN (2020 - f.founded) <= 10 THEN 1 ELSE 0 END * CASE WHEN s.year >= 2020 THEN 1 ELSE 0 END * t.teleworkable)     AS var7
        FROM panel_base s
        INNER JOIN remote_clean  r USING (companyname_c)
        INNER JOIN founding_clean f USING (companyname_c)
        INNER JOIN tele_clean     t USING (companyname_c);
        """
    )

    # 5) Export
    if output_format in {"parquet", "pq"}:
        con.execute(
            f"COPY (SELECT * FROM user_wage_panel) TO '{out_path}' (FORMAT 'parquet');"
        )
    elif output_format == "csv":
        con.execute(
            f"COPY (SELECT * FROM user_wage_panel) TO '{out_path}' (FORMAT 'csv', HEADER);"
        )
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    rowcount = con.execute("SELECT COUNT(*) FROM user_wage_panel;").fetchone()[0]
    print(f"✓ user_wage_panel written to {out_path}  (rows={rowcount:,})")


if __name__ == "__main__":
    main()
