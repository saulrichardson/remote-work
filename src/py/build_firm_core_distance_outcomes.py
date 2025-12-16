#!/usr/bin/env python3
"""Build firm-level core vs non-core geography outcomes for firm-scaling regressions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple, List, Sequence

import duckdb
import numpy as np
import pandas as pd
from haversine import haversine_vector, Unit

from project_paths import DATA_CLEAN, DATA_RAW, ensure_dir

DIST_THRESHOLDS_KM: Tuple[int, ...] = (50, 250)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "--linkedin",
        type=Path,
        default=DATA_CLEAN / "linkedin_panel_with_remote.parquet",
        help="LinkedIn firm×CBSA×half-year panel (parquet).",
    )
    parser.add_argument(
        "--spells",
        type=Path,
        help="Raw Scoop_workers_positions.csv; if provided, rebuild panel using user lookup.",
    )
    parser.add_argument(
        "--user-lookup",
        type=Path,
        default=DATA_CLEAN / "user_location_lookup.csv",
        help="User-level location lookup CSV (user_location_lookup.csv).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        help="DuckDB worker threads when rebuilding from --spells.",
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        help="Optional DuckDB temp directory when rebuilding from --spells.",
    )
    parser.add_argument(
        "--core",
        type=Path,
        default=DATA_CLEAN / "company_core_msas_by_half.csv",
        help="Core CBSA table (output of dispersion_metrics.py).",
    )
    parser.add_argument(
        "--msa-map",
        type=Path,
        default=DATA_CLEAN / "enriched_msa.csv",
        help="Lookup with columns cbsacode, lat, lon",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_CLEAN / "firm_core_distance_outcomes.csv",
        help="Destination CSV path",
    )
    return parser.parse_args()


def load_linkedin_panel(path: Path) -> pd.DataFrame:
    """Load existing firm×CBSA panel (numeric CBSAs only)."""

    if not path.exists():
        raise FileNotFoundError(path)
    con = duckdb.connect()
    query = f"""
        SELECT
            lower(trim(companyname)) AS companyname,
            CAST(yh AS BIGINT)       AS yh_raw,
            CAST(cbsa AS VARCHAR)    AS cbsa_text,
            SUM(headcount)           AS headcount,
            AVG(lat)                 AS lat,
            AVG(lon)                 AS lon
        FROM read_parquet('{path.as_posix()}')
        WHERE headcount IS NOT NULL
          AND headcount > 0
          AND cbsa IS NOT NULL
          AND regexp_matches(cbsa, '^[0-9]+$')
        GROUP BY 1,2,3
    """
    df = con.execute(query).fetch_df()
    con.close()
    if df.empty:
        raise RuntimeError("LinkedIn panel returned zero rows after filtering valid CBSAs.")
    df["cbsa"] = df["cbsa_text"].astype(int)
    df = df.drop(columns=["cbsa_text"])
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    # Stata year-half date baseline is 1960H1 → 3920
    df["yh"] = (df["yh_raw"] - 3920).astype(int)
    df.drop(columns=["yh_raw"], inplace=True)
    df["cbsa_from_lookup"] = 0
    return df


def build_panel_from_spells(
    spells_path: Path,
    msa_map_path: Path,
    user_lookup_path: Path,
    threads: int | None = None,
    temp_dir: str | None = None,
) -> pd.DataFrame:
    """Rebuild firm×CBSA×half-year headcounts using user_location_lookup to impute locations."""

    if not spells_path.exists():
        raise FileNotFoundError(spells_path)
    if not msa_map_path.exists():
        raise FileNotFoundError(msa_map_path)
    if not user_lookup_path.exists():
        raise FileNotFoundError(user_lookup_path)

    con = duckdb.connect()
    if threads:
        con.execute(f"PRAGMA threads={threads};")
    if temp_dir:
        safe = temp_dir.replace("'", "''")
        con.execute(f"PRAGMA temp_directory='{safe}';")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE spells AS
        SELECT
            CAST(user_id AS BIGINT) AS user_id,
            lower(trim(regexp_replace(companyname, ',+$', ''))) AS companyname,
            TRIM(msa) AS msa,
            COALESCE(TRY_CAST(start_date AS DATE), TRY_CAST(startdate AS DATE)) AS start_dt,
            COALESCE(
                TRY_CAST(end_date AS DATE),
                TRY_CAST(enddate AS DATE),
                TRY_CAST(start_date AS DATE),
                TRY_CAST(startdate AS DATE)
            ) AS end_dt
        FROM read_csv_auto('{spells_path.as_posix()}',
            header=true,
            strict_mode=false,
            ignore_errors=true,
            union_by_name=true,
            sample_size=2000000,
            null_padding=true,
            parallel=false)
        WHERE companyname IS NOT NULL
          AND start_date IS NOT NULL;
        """
    )

    con.execute("DELETE FROM spells WHERE start_dt IS NULL;")
    con.execute("UPDATE spells SET end_dt = start_dt WHERE end_dt < start_dt;")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE msa_map AS
        SELECT
            TRIM(msa) AS msa,
            CAST(cbsacode AS VARCHAR) AS cbsa,
            CAST(lat AS DOUBLE) AS lat,
            CAST(lon AS DOUBLE) AS lon
        FROM read_csv_auto('{msa_map_path.as_posix()}', header=true, ignore_errors=true)
        WHERE cbsacode IS NOT NULL;
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE user_lookup AS
        SELECT *
        FROM (
            SELECT
                CAST(user_id AS BIGINT) AS user_id,
                TRIM(CAST(cbsa AS VARCHAR)) AS cbsa,
                TRY_CAST(latitude AS DOUBLE) AS lat_lookup,
                TRY_CAST(longitude AS DOUBLE) AS lon_lookup
            FROM read_csv_auto('{user_lookup_path.as_posix()}',
                header=true,
                union_by_name=true,
                ignore_errors=true)
        )
        WHERE cbsa IS NOT NULL AND cbsa <> '';
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE spell_geo AS
        SELECT
            s.user_id,
            s.companyname,
            COALESCE(m.cbsa, ul.cbsa) AS cbsa,
            COALESCE(m.lat, ul.lat_lookup) AS lat,
            COALESCE(m.lon, ul.lon_lookup) AS lon,
            CASE WHEN m.cbsa IS NULL AND ul.cbsa IS NOT NULL THEN 1 ELSE 0 END AS cbsa_from_lookup,
            date_trunc('month', s.start_dt) AS start_m,
            date_trunc('month', s.end_dt)   AS end_m
        FROM spells s
        LEFT JOIN msa_map m USING (msa)
        LEFT JOIN user_lookup ul USING (user_id)
        WHERE (m.cbsa IS NOT NULL OR ul.cbsa IS NOT NULL);
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE month_expanded AS
        SELECT
            companyname,
            cbsa,
            cbsa_from_lookup,
            lat,
            lon,
            gen.mon AS mon,
            user_id
        FROM spell_geo sg
        JOIN generate_series(sg.start_m, sg.end_m, INTERVAL '1 month') AS gen(mon) ON TRUE;
        """
    )

    df = con.execute(
        """
        WITH base AS (
            SELECT
                companyname,
                cbsa,
                cbsa_from_lookup,
                lat,
                lon,
                ((year(mon) - 1960) * 2 + CASE WHEN month(mon) > 6 THEN 1 ELSE 0 END) AS yh,
                user_id
            FROM month_expanded
        )
        SELECT
            companyname,
            CAST(cbsa AS VARCHAR) AS cbsa_text,
            MAX(cbsa_from_lookup) AS cbsa_from_lookup,
            yh,
            AVG(lat) AS lat,
            AVG(lon) AS lon,
            COUNT(DISTINCT user_id) AS headcount
        FROM base
        GROUP BY companyname, cbsa, yh
        HAVING COUNT(DISTINCT user_id) > 0
        ORDER BY companyname, yh, cbsa;
        """
    ).fetch_df()

    con.close()

    if df.empty:
        raise RuntimeError("No rows produced when rebuilding panel from spells/user lookup.")

    df = df[df["cbsa_text"].str.match(r"^[0-9]+$")]
    if df.empty:
        raise RuntimeError("All rows had non-numeric CBSA after rebuild; check lookup inputs.")
    df["cbsa"] = df["cbsa_text"].astype(int)
    df = df.drop(columns=["cbsa_text"])
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    df["yh"] = df["yh"].astype(int)
    df["headcount"] = df["headcount"].astype(int)
    df["cbsa_from_lookup"] = df["cbsa_from_lookup"].astype(int)
    return df


def load_core_table(core_path: Path, msa_map_path: Path) -> pd.DataFrame:
    if not core_path.exists():
        raise FileNotFoundError(core_path)
    core = pd.read_csv(core_path)
    required = {"companyname", "year", "half", "cbsa"}
    missing = required - set(core.columns)
    if missing:
        raise ValueError(f"Core table missing columns: {sorted(missing)}")
    core = core.dropna(subset=["companyname", "year", "half", "cbsa"])
    core["companyname"] = core["companyname"].str.strip().str.lower()
    core["year"] = core["year"].astype(int)
    core["half"] = core["half"].astype(int)
    core["cbsa"] = core["cbsa"].astype(int)
    core["yh"] = (core["year"] - 1960) * 2 + (core["half"] - 1)

    if not msa_map_path.exists():
        raise FileNotFoundError(msa_map_path)
    msa_map = pd.read_csv(msa_map_path, usecols=["cbsacode", "lat", "lon"])
    msa_map = msa_map.dropna(subset=["cbsacode", "lat", "lon"])
    msa_map["cbsa"] = pd.to_numeric(msa_map["cbsacode"], errors="coerce").astype("Int64")
    msa_map = msa_map.dropna(subset=["cbsa"]).drop_duplicates(subset=["cbsa"])
    msa_map = msa_map.rename(columns={"lat": "core_lat", "lon": "core_lon"})

    core = core.merge(msa_map[["cbsa", "core_lat", "core_lon"]], on="cbsa", how="left")
    core = core.dropna(subset=["core_lat", "core_lon"])
    if core.empty:
        raise RuntimeError("Core table has no rows with resolved lat/lon coordinates.")
    return core


def build_core_lookup(core: pd.DataFrame) -> Dict[Tuple[str, int], np.ndarray]:
    lookup: Dict[Tuple[str, int], np.ndarray] = {}
    for (company, yh), g in core.groupby(["companyname", "yh"]):
        coords = g[["core_lat", "core_lon"]].to_numpy()
        if len(coords):
            lookup[(company, yh)] = coords
    if not lookup:
        raise RuntimeError("No core coordinate groups were created.")
    return lookup


def attach_core_flags(df: pd.DataFrame, core_keys: pd.DataFrame) -> pd.DataFrame:
    key = core_keys[["companyname", "yh", "cbsa"]].drop_duplicates()
    df = df.merge(key.assign(is_core=1), on=["companyname", "yh", "cbsa"], how="left")
    df["is_core"] = df["is_core"].fillna(0).astype(np.int8)
    valid_pairs = core_keys[["companyname", "yh"]].drop_duplicates()
    merged = df.merge(valid_pairs.assign(has_core=1), on=["companyname", "yh"], how="inner")
    merged = merged.drop(columns=["has_core"])
    if merged.empty:
        raise RuntimeError("No firm×half-year rows survived the core inner join.")
    return merged


def attach_distances(df: pd.DataFrame, core_lookup: Dict[Tuple[str, int], np.ndarray]) -> pd.DataFrame:
    distances = np.full(len(df), np.nan, dtype=float)
    grouped_indices = df.groupby(["companyname", "yh"]).indices
    for (company, yh), idx in grouped_indices.items():
        cores = core_lookup.get((company, yh))
        if cores is None or not len(cores):
            raise RuntimeError(f"Missing core coordinates for company={company} yh={yh}.")
        rows = df.iloc[idx]
        latlon = rows[["lat", "lon"]].to_numpy()
        mask = np.any(np.isnan(latlon), axis=1)
        valid_positions = np.where(~mask)[0]
        if valid_positions.size:
            subset = latlon[valid_positions]
            dists = haversine_vector(subset, cores, Unit.KILOMETERS, comb=True)
            dists = dists.reshape(subset.shape[0], cores.shape[0])
            min_dists = dists.min(axis=1)
            distances[idx[valid_positions]] = min_dists
    df = df.copy()
    df["dist_to_core_km"] = distances
    return df


def weighted_average(values: np.ndarray, weights: np.ndarray) -> float:
    mask = (~np.isnan(values)) & (weights > 0)
    if not mask.any():
        return np.nan
    return float(np.average(values[mask], weights=weights[mask]))


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    mask = (~np.isnan(values)) & (weights > 0)
    if not mask.any():
        return np.nan
    v = values[mask]
    w = weights[mask]
    sorter = np.argsort(v)
    v = v[sorter]
    w = w[sorter]
    cum = np.cumsum(w)
    target = quantile * w.sum()
    idx = np.searchsorted(cum, target, side="right")
    idx = min(idx, len(v) - 1)
    return float(v[idx])


def summarize_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (company, yh), g in df.groupby(["companyname", "yh"], sort=False):
        total = g["headcount"].sum()
        if total <= 0:
            raise RuntimeError(f"Non-positive headcount for {(company, yh)}")
        imputed_head = g.loc[g.get("cbsa_from_lookup", 0) == 1, "headcount"].sum()
        core_head = g.loc[g["is_core"] == 1, "headcount"].sum()
        noncore_head = total - core_head
        dist_values = g["dist_to_core_km"].to_numpy()
        weights = g["headcount"].to_numpy()

        record = {
            "companyname": company,
            "yh": int(yh),
            "total_headcount": total,
            "imputed_headcount": imputed_head,
            "imputed_share": imputed_head / total if total > 0 else np.nan,
            "core_headcount": core_head,
            "noncore_headcount": noncore_head,
            "core_share": core_head / total,
            "noncore_share": noncore_head / total,
            "avg_distance_km": weighted_average(dist_values, weights),
            "p90_distance_km": weighted_quantile(dist_values, weights, 0.90),
            "noncore_core_ratio": (noncore_head / core_head) if core_head > 0 else np.nan,
            "core_minus_noncore": core_head - noncore_head,
            "num_noncore_cbsa": g.loc[g["is_core"] == 0, "cbsa"].nunique(),
        }

        for threshold in DIST_THRESHOLDS_KM:
            mask = (dist_values >= threshold) & (~np.isnan(dist_values))
            far_head = g.loc[mask, "headcount"].sum()
            record[f"headcount_far_{threshold:03d}"] = far_head
            record[f"share_far_{threshold:03d}"] = far_head / total
            record[f"any_far_{threshold:03d}"] = int(far_head > 0)

        records.append(record)
    return pd.DataFrame(records)


def main() -> None:
    args = parse_args()
    ensure_dir(args.output.parent)

    if args.spells:
        linkedin = build_panel_from_spells(
            spells_path=args.spells,
            msa_map_path=args.msa_map,
            user_lookup_path=args.user_lookup,
            threads=args.threads,
            temp_dir=args.temp_dir,
        )
    else:
        linkedin = load_linkedin_panel(args.linkedin)

    core = load_core_table(args.core, args.msa_map)
    lookup = build_core_lookup(core)

    tagged = attach_core_flags(linkedin, core)
    tagged = attach_distances(tagged, lookup)

    summary = summarize_outcomes(tagged)
    summary.sort_values(["companyname", "yh"], inplace=True)
    summary.to_csv(args.output, index=False)
    print(f"✓ wrote {len(summary):,} firm×half-year rows → {args.output}")


if __name__ == "__main__":
    main()
