"""Build firm × SOC × MSA × half-year panel from the raw LinkedIn job-spell dump.

This implementation relies on DuckDB, which can stream-read the ~10 GB CSV
without loading it fully into memory while still pushing vectorised SQL
operations (including the month-level expansion) in parallel.

The script performs the following steps:

1.  Read only the necessary columns from ``Scoop_workers_positions.csv``.
2.  Create a clean 6-digit SOC code (``soc6``).
3.  Merge the textual LinkedIn MSA with an enriched table that provides the
    CBSA code *and* lat/lon; rows that do not map ("empty" or NONMETRO areas)
    are dropped.
4.  Convert start/end dates to the first day of their month and expand each
    spell to one row per month via ``generate_series``.
5.  Collapse month-level rows to half-year frequency, computing head-count,
    joins, and leaves.
6.  Write the resulting panel to Parquet (or CSV / Stata if desired).

The SQL is executed entirely inside DuckDB so the host Python process never
materialises the exploded table.  On a 32-core machine the full pipeline runs
in under 10 minutes while staying below ~8 GB of RAM.

Usage
-----
python py/build_linkedin_panel_duckdb.py \
       --spells     data/raw/Scoop_workers_positions.csv \
       --msa-map    data/clean/enriched_msa.csv      \
       --output     data/clean/linkedin_firm_soc_msa_yh.parquet

Optional flags:
    --threads N          number of DuckDB threads (default: all cores)
    --sample N           read only the first N rows *for testing*
    --format {parquet,csv}   output format (default: parquet)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import math
import os
import sys

# We attempt to import DuckDB; if unavailable we fall back to a (slow but
# functional) pandas implementation that is suitable for small samples and for
# environments where installing additional binaries is not possible.
#
# The DuckDB path is recommended for production runs on the full 10 GB file
# because it finishes 10× faster and keeps memory usage low.  The pandas path
# is automatically invoked when DuckDB cannot be imported **and** the caller
# supplies --sample (to keep runtime reasonable).

try:
    import duckdb as _dk  # type: ignore

    _HAVE_DUCKDB = True
except ModuleNotFoundError:  # pragma: no cover  -- fallback environment
    _HAVE_DUCKDB = False

import pandas as _pd
import numpy as _np

from project_paths import DATA_PROCESSED

USER_CBSA_CSV = DATA_PROCESSED / "user_location_lookup.csv"
VALID_LOOKUP_MATCHES = (
    "alias",
    "principal_city",
    "principal_city_altstate",
    "principal_city_state_guess",
    "nearest_cbsa_state",
    "nearest_cbsa_cross_state",
)

LOOKUP_PRIORITY_SQL = "CASE match_quality " \
    "WHEN 'alias' THEN 1 " \
    "WHEN 'principal_city' THEN 2 " \
    "WHEN 'principal_city_altstate' THEN 3 " \
    "WHEN 'principal_city_state_guess' THEN 4 " \
    "WHEN 'nearest_cbsa_state' THEN 5 " \
    "WHEN 'nearest_cbsa_cross_state' THEN 6 " \
    "ELSE 9 END"

LOOKUP_PRIORITY = {
    "alias": 1,
    "principal_city": 2,
    "principal_city_altstate": 3,
    "principal_city_state_guess": 4,
    "nearest_cbsa_state": 5,
    "nearest_cbsa_cross_state": 6,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(__doc__, formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument("--spells", required=True, help="Path to Scoop_workers_positions.csv")
    p.add_argument(
        "--msa-map",
        required=True,
        help="CSV with columns: msa,cbsacode,lat,lon (enriched_msa.csv)",
    )
    p.add_argument(
        "--output",
        required=True,
        help="Destination file (extension determines format unless --format given)",
    )
    p.add_argument(
        "--threads",
        type=int,
        default=None,
        help="DuckDB threads (default: all cores)",
    )
    p.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Load only the first N rows – for quick testing",
    )
    p.add_argument(
        "--format",
        choices=("parquet", "csv"),
        help="Force output format (otherwise derived from --output extension)",
    )
    p.add_argument(
        "--temp-dir",
        help="Directory for DuckDB temporary spill files (overrides PRAGMA temp_directory).",
    )

    return p.parse_args()


def _infer_output_format(path: str, explicit: str | None) -> str:
    if explicit:
        return explicit.lower()
    ext = os.path.splitext(path)[1].lower()
    if ext in {".parquet", ".pq"}:
        return "parquet"
    if ext in {".csv", ".gz"}:
        return "csv"
    raise ValueError("Cannot infer output format; please pass --format")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: C901  <-- complexity fine for standalone script
    ns = _parse_args()

    out_format = _infer_output_format(ns.output, ns.format)

    # ------------------------------------------------------------------
    # Preferred path: DuckDB is available.
    # ------------------------------------------------------------------
    if _HAVE_DUCKDB:
        con = _dk.connect()

        # Configure temp spill directory to avoid hitting home quota.
        tmp_dir = ns.temp_dir or os.environ.get("VAST") or os.environ.get("DUCKDB_TEMP_DIRECTORY")
        if tmp_dir:
            # Ensure directory exists; DuckDB will error otherwise.
            if not os.path.isdir(tmp_dir):
                os.makedirs(tmp_dir, exist_ok=True)
            safe_tmp = tmp_dir.replace("'", "''")
            con.execute(f"PRAGMA temp_directory='{safe_tmp}';")

        if ns.threads:
            con.execute(f"PRAGMA threads={ns.threads};")

        # 1) MSA map
        con.execute(
            f"""
            CREATE TEMP TABLE msa_map AS
            SELECT
                TRIM(msa) AS msa,
                CAST(cbsacode AS VARCHAR) AS cbsa,
                CAST(lat AS DOUBLE) AS lat,
                CAST(lon AS DOUBLE) AS lon
            FROM read_csv_auto('{ns.msa_map}', header=True);
            """
        ) 

        limit_clause = "" if ns.sample is None else f"LIMIT {ns.sample}"

        if not USER_CBSA_CSV.exists():
            raise FileNotFoundError(USER_CBSA_CSV)

        priority_case = LOOKUP_PRIORITY_SQL
        con.execute(
            f"""
            CREATE TEMP TABLE user_cbsa AS
            WITH raw AS (
                SELECT
                    CAST(user_id AS BIGINT) AS user_id,
                    cbsa,
                    TRY_CAST(latitude AS DOUBLE) AS lat,
                    TRY_CAST(longitude AS DOUBLE) AS lon,
                    match_quality,
                    ROW_NUMBER() OVER (
                        PARTITION BY CAST(user_id AS BIGINT)
                        ORDER BY {priority_case}
                    ) AS rn
                FROM read_csv_auto(
                    '{USER_CBSA_CSV.as_posix()}',
                    header=true,
                    all_varchar=true,
                    ignore_errors=true
                )
                WHERE cbsa IS NOT NULL
                  AND match_quality IN ({", ".join(repr(m) for m in VALID_LOOKUP_MATCHES)})
            )
            SELECT user_id, cbsa, lat, lon
            FROM raw
            WHERE rn = 1;
            """
        )

        con.execute(
            f"""
            CREATE TEMP VIEW spells AS
            SELECT
                CAST(user_id AS BIGINT)       AS user_id,
                companyname,
                TRY_CAST(start_date AS DATE)      AS start_date,
                TRY_CAST(end_date   AS DATE)      AS end_date,
                soc_2010,
                soc6d,
                msa
            FROM read_csv_auto(
                '{ns.spells}',
                header=true,
                strict_mode=false,
                all_varchar=true,
                ignore_errors=true,
                null_padding=true
            )
            {limit_clause};
            """
        )

        # 3) Clean + merge MSA + SOC
        con.execute(
            """
            CREATE TEMP VIEW spells2 AS
            SELECT
                s.user_id,
                lower(trim(regexp_replace(s.companyname, ',+$', ''))) AS companyname,
                regexp_replace(COALESCE(s.soc_2010, s.soc6d), '-', '', 'g') AS soc6,
                date_trunc('month', s.start_date) AS start_m,
                date_trunc('month', COALESCE(s.end_date, current_date)) AS end_m,
                COALESCE(m.cbsa, uc.cbsa) AS cbsa,
                CASE WHEN m.cbsa IS NULL AND uc.cbsa IS NOT NULL THEN 1 ELSE 0 END AS cbsa_from_lookup,
                COALESCE(m.lat, uc.lat) AS lat,
                COALESCE(m.lon, uc.lon) AS lon
            FROM spells AS s
            LEFT JOIN msa_map AS m USING (msa)
            LEFT JOIN user_cbsa AS uc USING (user_id)
            WHERE (m.cbsa IS NOT NULL OR uc.cbsa IS NOT NULL)
              AND s.companyname IS NOT NULL
              AND s.start_date IS NOT NULL
              AND COALESCE(s.soc_2010, s.soc6d) IS NOT NULL;
            """
        )

        # 4) Month expansion + flags
        con.execute(
            """
            CREATE TEMP VIEW month_expanded AS
            SELECT
                user_id,
                companyname,
                soc6,
                cbsa,
                cbsa_from_lookup,
                lat,
                lon,
                mon,
                (mon = start_m)::INTEGER AS join_flag,
                (mon = end_m)::INTEGER   AS leave_flag
            FROM spells2
            JOIN generate_series(start_m, end_m, INTERVAL '1 month') AS gen(mon) ON TRUE;
            """
        )

        # 5) Half-year aggregation
        con.execute(
            """
            CREATE TEMP VIEW half_year AS
            SELECT
                companyname,
                soc6,
                cbsa,
                MAX(cbsa_from_lookup) AS cbsa_from_lookup,
                ((year(mon) * 2) + (CASE WHEN month(mon) > 6 THEN 1 ELSE 0 END)) AS yh,
                ANY_VALUE(lat) AS lat,
                ANY_VALUE(lon) AS lon,
                COUNT(DISTINCT user_id) AS headcount,
                COUNT(DISTINCT CASE WHEN join_flag = 1  THEN user_id END) AS joins,
                COUNT(DISTINCT CASE WHEN leave_flag = 1 THEN user_id END) AS leaves
            FROM month_expanded
            GROUP BY 1,2,3,5;
            """
        )

        # 6) Persist
        if out_format == "parquet":
            con.execute(f"COPY half_year TO '{ns.output}' (FORMAT 'parquet');")
        else:
            con.execute(f"COPY half_year TO '{ns.output}' (HEADER, DELIMITER ',');")

        print(f"✓ Panel written to {ns.output} using DuckDB")
        return

    # ------------------------------------------------------------------
    # Fallback path: DuckDB is unavailable.  Only allowed when --sample is
    # provided (otherwise the job would be far too slow / memory hungry).
    # ------------------------------------------------------------------

    if ns.sample is None:
        sys.exit(
            "duckdb module not found and no --sample specified.  Either install"
            " duckdb or run the script with --sample <N> to build a small test"
            " extract with pandas."
        )

    print("duckdb not available → falling back to pandas for a sample run (this is" " okay for small --sample sizes).", file=sys.stderr)

    # 1) Load MSA map into pandas
    msa_df = _pd.read_csv(ns.msa_map, usecols=["msa", "cbsacode", "lat", "lon"])
    msa_df = msa_df.dropna(subset=["cbsacode"])
    msa_df["cbsacode"] = msa_df["cbsacode"].astype(str)

    # 2) Read sample rows from spells
    spell_df = _pd.read_csv(
        ns.spells,
        nrows=ns.sample,
        usecols=[
            "user_id",
            "companyname",
            "start_date",
            "end_date",
            "soc_2010",
            "soc6d",
            "msa",
        ],
        parse_dates=["start_date", "end_date"],
    )

    # 3) Pre-clean
    spell_df = spell_df.dropna(subset=["companyname", "start_date"])
    spell_df["soc6"] = (
        spell_df["soc_2010"].fillna(spell_df["soc6d"]).str.replace("-", "", regex=False)
    )
    spell_df = spell_df.dropna(subset=["soc6"])

    msa_df = msa_df.rename(columns={"cbsacode": "cbsa_map"})
    spell_df = spell_df.merge(msa_df, on="msa", how="left")

    if USER_CBSA_CSV.exists():
        lookup_df = _pd.read_csv(
            USER_CBSA_CSV,
            usecols=["user_id", "cbsa", "latitude", "longitude", "match_quality"],
        )
        lookup_df = lookup_df[lookup_df["match_quality"].isin(VALID_LOOKUP_MATCHES)]
        lookup_df = lookup_df.rename(
            columns={
                "cbsa": "cbsa_lookup",
                "latitude": "lat_lookup",
                "longitude": "lon_lookup",
            }
        ).drop(columns=["match_quality"])
        spell_df = spell_df.merge(lookup_df, on="user_id", how="left")
    else:
        spell_df["cbsa_lookup"] = _pd.NA
        spell_df["lat_lookup"] = _pd.NA
        spell_df["lon_lookup"] = _pd.NA

    spell_df["cbsa_from_lookup"] = (
        spell_df["cbsa_map"].isna() & spell_df["cbsa_lookup"].notna()
    ).astype("int8")
    spell_df["cbsacode"] = spell_df["cbsa_map"].fillna(spell_df["cbsa_lookup"])
    spell_df["lat"] = spell_df["lat"].fillna(spell_df["lat_lookup"])
    spell_df["lon"] = spell_df["lon"].fillna(spell_df["lon_lookup"])
    spell_df = spell_df.dropna(subset=["cbsacode"])
    spell_df = spell_df.drop(columns=["lat_lookup", "lon_lookup", "cbsa_lookup"])

    # 4) Month expansion in pandas (ok for small sample)
    def _expand_months(row: _pd.Series) -> _pd.DataFrame:
        start = row.start_date.to_period("M")
        end = (row.end_date if _pd.notna(row.end_date) else _pd.Timestamp.today()).to_period("M")
        months = _pd.period_range(start, end, freq="M")
        df = _pd.DataFrame({"mon": months.to_timestamp(), "join_flag": 0, "leave_flag": 0})
        df.loc[0, "join_flag"] = 1
        df.loc[len(df) - 1, "leave_flag"] = 1
        for col in ["user_id", "companyname", "soc6", "cbsacode", "cbsa_from_lookup", "lat", "lon"]:
            df[col] = row[col]
        return df

    expanded = _pd.concat((_expand_months(r) for _, r in spell_df.iterrows()), ignore_index=True)

    # 5) Half-year aggregation
    expanded["year"] = expanded["mon"].dt.year
    expanded["half"] = (expanded["mon"].dt.month > 6).astype(int)
    expanded["yh"] = expanded["year"] * 2 + expanded["half"]

    grouped = (
        expanded.groupby(["companyname", "soc6", "cbsacode", "cbsa_from_lookup", "yh"])
        .agg(
            headcount=("user_id", "nunique"),
            joins=("join_flag", "sum"),
            leaves=("leave_flag", "sum"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            cbsa_from_lookup=("cbsa_from_lookup", "max"),
        )
        .reset_index()
        .rename(columns={"cbsacode": "cbsa"})
    )

    # 6) Output
    if out_format == "parquet":
        grouped.to_parquet(ns.output, index=False)
    else:
        grouped.to_csv(ns.output, index=False)

    print(f"✓ Panel sample written to {ns.output} using pandas fallback")


if __name__ == "__main__":
    main()
