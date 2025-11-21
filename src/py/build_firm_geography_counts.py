#!/usr/bin/env python3
"""Aggregate firm-level counts of unique locations, MSAs, and states by half-year."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import duckdb

DEFAULT_SPELLS = Path("data/raw/Scoop_workers_positions.csv")
DEFAULT_OUTPUT = Path("data/cleaned/firm_geography_counts.csv")
DEFAULT_USER_LOOKUP = Path("data/clean/user_location_lookup.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--spells", default=str(DEFAULT_SPELLS), help="Path to Scoop_workers_positions.csv")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Destination file (csv or parquet)")
    parser.add_argument(
        "--user-lookup",
        default=str(DEFAULT_USER_LOOKUP),
        help="CSV with user-level location lookup (user_location_lookup.csv)",
    )
    parser.add_argument("--threads", type=int, help="Optional DuckDB thread count")
    parser.add_argument("--temp-dir", help="Directory for DuckDB temp storage")
    parser.add_argument("--sample", type=int, help="Limit number of rows read from spells (debug)")
    return parser.parse_args()


def main() -> None:
    ns = parse_args()
    spells_path = Path(ns.spells)
    if not spells_path.exists():
        raise FileNotFoundError(spells_path)

    lookup_path = Path(ns.user_lookup)
    if not lookup_path.exists():
        raise FileNotFoundError(lookup_path)

    out_path = Path(ns.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_ext = out_path.suffix.lower()

    con = duckdb.connect()

    if ns.threads:
        con.execute(f"PRAGMA threads={ns.threads};")

    temp_dir = ns.temp_dir or os.environ.get("DUCKDB_TEMP_DIRECTORY")
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        safe_tmp = temp_dir.replace("'", "''")
        con.execute(f"PRAGMA temp_directory='{safe_tmp}';")

    limit_clause = f"LIMIT {ns.sample}" if ns.sample else ""

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE user_lookup AS
        SELECT
            CAST(user_id AS BIGINT) AS user_id,
            NULLIF(UPPER(TRIM(state_assigned)), '') AS state_assigned,
            NULLIF(TRIM(cbsa_title), '') AS cbsa_title
        FROM read_csv_auto(
            '{lookup_path.as_posix()}',
            header=true,
            union_by_name=true,
            ignore_errors=true
        );
        """
    )

    # Clean spells and keep only the columns we care about
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE spells_clean AS
        WITH base AS (
            SELECT
                CAST(user_id AS BIGINT) AS user_id,
                LOWER(TRIM(REGEXP_REPLACE(companyname, ',+$', ''))) AS companyname_c,
                TRIM(location) AS location_trim,
                LOWER(TRIM(location)) AS location_norm,
                state,
                TRIM(msa) AS msa_trim,
                COALESCE(TRY_CAST(start_date AS DATE), TRY_CAST(startdate AS DATE)) AS start_dt,
                COALESCE(
                    TRY_CAST(end_date AS DATE),
                    TRY_CAST(enddate AS DATE),
                    TRY_CAST(start_date AS DATE),
                    TRY_CAST(startdate AS DATE)
                ) AS end_dt
            FROM read_csv_auto(
                '{spells_path.as_posix()}',
                header=true,
                strict_mode=false,
                ignore_errors=true,
                union_by_name=true,
                sample_size=2000000,
                null_padding=true,
                parallel=false
            )
            {limit_clause}
        )
        SELECT
            user_id,
            companyname_c,
            CASE
                WHEN remote_flag = 1 THEN NULL
                ELSE NULLIF(location_trim, '')
            END AS location_clean,
            CASE
                WHEN remote_flag = 1 THEN NULL
                WHEN state IS NULL OR TRIM(state) = '' OR LOWER(TRIM(state)) = 'empty' THEN NULL
                ELSE UPPER(TRIM(state))
            END AS state_clean,
            CASE
                WHEN remote_flag = 1 THEN NULL
                ELSE CASE
                    WHEN msa_trim IS NULL OR TRIM(msa_trim) = '' THEN NULL
                    WHEN LOWER(TRIM(msa_trim)) = 'empty' THEN NULL
                    ELSE TRIM(msa_trim)
                END
            END AS msa_clean,
            start_dt,
            end_dt
        FROM (
            SELECT *,
                CASE
                    WHEN location_trim IS NULL OR location_trim = '' THEN 0
                    WHEN regexp_matches(location_norm, '(remote|work\\s*from\\s*home|wfh|worldwide|global|virtual|distributed|anywhere)') THEN 1
                    ELSE 0
                END AS remote_flag
            FROM base
        );
        """
    )

    con.execute("DELETE FROM spells_clean WHERE companyname_c IS NULL OR start_dt IS NULL;")
    con.execute("UPDATE spells_clean SET end_dt = start_dt WHERE end_dt < start_dt;")

    # Expand each spell to half-year periods
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE spell_halves AS
        WITH bounds AS (
            SELECT
                companyname_c,
                user_id,
                location_clean,
                state_clean,
                msa_clean,
                state_assigned,
                cbsa_title,
                start_dt,
                end_dt,
                CASE
                    WHEN EXTRACT(month FROM start_dt) <= 6
                        THEN DATE_TRUNC('year', start_dt)
                    ELSE DATE_TRUNC('year', start_dt) + INTERVAL '6 months'
                END AS first_half,
                CASE
                    WHEN EXTRACT(month FROM end_dt) <= 6
                        THEN DATE_TRUNC('year', end_dt)
                    ELSE DATE_TRUNC('year', end_dt) + INTERVAL '6 months'
                END AS last_half
            FROM spells_clean sc
            LEFT JOIN user_lookup ul USING (user_id)
        )
        SELECT
            companyname_c,
            location_clean,
            state_clean,
            msa_clean,
            state_assigned,
            cbsa_title,
            gs.half_start AS half_start,
            EXTRACT(year FROM gs.half_start)::INT AS year,
            CASE WHEN EXTRACT(month FROM gs.half_start) = 1 THEN 1 ELSE 2 END AS half
        FROM bounds b,
        LATERAL generate_series(first_half, last_half, INTERVAL '6 months') AS gs(half_start);
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE firm_geo_counts AS
        SELECT
            companyname_c AS companyname,
            year,
            half,
            ((year - 1960) * 2 + (half - 1)) AS yh,
            COALESCE(COUNT(DISTINCT state_clean), 0) AS n_states,
            COALESCE(COUNT(DISTINCT msa_clean), 0) AS n_msas,
            COALESCE(COUNT(DISTINCT location_clean), 0) AS n_locations,
            COALESCE(COUNT(DISTINCT state_imputed), 0) AS n_states_imputed,
            COALESCE(COUNT(DISTINCT msa_imputed), 0) AS n_msas_imputed,
            COALESCE(COUNT(DISTINCT location_imputed), 0) AS n_locations_imputed
        FROM (
            SELECT
                companyname_c,
                year,
                half,
                state_clean,
                msa_clean,
                location_clean,
                NULLIF(COALESCE(state_clean, state_assigned), '') AS state_imputed,
                NULLIF(COALESCE(msa_clean, cbsa_title), '') AS msa_imputed,
                NULLIF(
                    COALESCE(
                        location_clean,
                        msa_clean,
                        cbsa_title,
                        state_clean,
                        state_assigned
                    ),
                    ''
                ) AS location_imputed
            FROM spell_halves
        ) sub
        GROUP BY 1,2,3
        ORDER BY 1,2,3;
        """
    )

    if out_ext in {".parquet", ".pq"}:
        con.execute(f"COPY firm_geo_counts TO '{out_path.as_posix()}' (FORMAT PARQUET);")
    else:
        con.execute(f"COPY firm_geo_counts TO '{out_path.as_posix()}' (HEADER, DELIMITER ',');")

    con.close()


if __name__ == "__main__":
    main()
