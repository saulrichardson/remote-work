#!/usr/bin/env python3
"""Build the enriched firm x half-year equity panel used by the active paper lane.

This script extends the canonical `latest_firm_yh_llm_equity.csv` by adding:
1) alternative equity measures (raw, strict-context, software-only),
2) discrete firm-level bins (median / top quartile / top quintile),
3) backfill audit statuses that separate:
   - no postings,
   - postings but no keyword-hit,
   - keyword-hit but no parseable LLM label,
   - observed true zero,
   - observed positive.

Inputs
------
- posting-level LLM merge:
    results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv
- equity candidates parquet:
    results/raw/postings_description_equity/equity_candidates.parquet
- firm panel:
    data/clean/firm_panel_with_cb.csv
- postings-description shards for full posting coverage counts:
    data/raw/postings_description/*.csv

Outputs
-------
- enriched firm x yh panel:
    results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv
- audit summary:
    results/raw/postings_description_equity/firm_merge/latest_llm_equity_backfill_audit_summary.csv
- audit by startup status:
    results/raw/postings_description_equity/firm_merge/latest_llm_equity_backfill_audit_by_startup.csv
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

from src.py.project_paths import DATA_CLEAN, DATA_RAW, RESULTS_RAW, ensure_dir, require_file


POSTINGS_MERGE_DEFAULT = (
    RESULTS_RAW / "postings_description_equity" / "firm_merge" / "latest_postings_llm_firm_merge.csv"
)
EQUITY_CANDIDATES_DEFAULT = RESULTS_RAW / "postings_description_equity" / "equity_candidates.parquet"
FIRM_PANEL_DEFAULT = DATA_CLEAN / "firm_panel_with_cb.csv"
OUT_DIR_DEFAULT = RESULTS_RAW / "postings_description_equity" / "firm_merge"


SOFTWARE_TEXT_RE = re.compile(
    r"(?:software|developer|programmer|devops|site reliability|sre|full[- ]?stack|"
    r"back[- ]?end|front[- ]?end|machine learning|ml engineer|data engineer|"
    r"platform engineer|application engineer|security engineer|qa engineer)",
    flags=re.IGNORECASE,
)

SOFTWARE_ROLE_RE = re.compile(
    r"(?:software|developer|engineer|devops|site reliability|sre|machine learning|"
    r"data engineer|platform engineer|security engineer|qa engineer)",
    flags=re.IGNORECASE,
)


def default_input_glob() -> str:
    return str(DATA_RAW / "postings_description" / "*.csv")


def sql_quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--postings-merge-csv",
        type=Path,
        default=POSTINGS_MERGE_DEFAULT,
        help=f"Posting-level LLM merge CSV (default: {POSTINGS_MERGE_DEFAULT}).",
    )
    p.add_argument(
        "--candidates-parquet",
        type=Path,
        default=EQUITY_CANDIDATES_DEFAULT,
        help=f"Equity candidates parquet (default: {EQUITY_CANDIDATES_DEFAULT}).",
    )
    p.add_argument(
        "--firm-panel-csv",
        type=Path,
        default=FIRM_PANEL_DEFAULT,
        help=f"Firm panel CSV (default: {FIRM_PANEL_DEFAULT}).",
    )
    p.add_argument(
        "--input-glob",
        default=default_input_glob(),
        help="Glob for full postings-description shards (default: auto-detected).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR_DEFAULT,
        help=f"Output directory (default: {OUT_DIR_DEFAULT}).",
    )
    p.add_argument(
        "--run-label",
        type=str,
        default="",
        help="Optional output prefix (default: enriched_equity).",
    )
    return p.parse_args()


def normalize_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    out = str(value).strip().lower()
    if out in {"", "nan", "none"}:
        return None
    return out


def normalize_job_id(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    s = s.str.replace(r"\.0+$", "", regex=True)
    s = s.where(~s.str.lower().isin(["", "nan", "none"]), other=pd.NA)
    return s


def normalize_firm_id(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    return s.where(~s.isin(["", "nan", "none"]), other=pd.NA)


def add_halfyear_date(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    month = np.where(dt.dt.month <= 6, 1, 7)
    yh = pd.to_datetime({"year": dt.dt.year, "month": month, "day": 1}, errors="coerce")
    return yh.dt.strftime("%Y-%m-%d")


def to_bool(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    out = pd.Series(pd.NA, index=series.index, dtype="boolean")
    out.loc[s.isin(["true", "1", "t", "yes"])] = True
    out.loc[s.isin(["false", "0", "f", "no"])] = False
    return out


def require_columns(frame: pd.DataFrame, columns: Iterable[str], *, context: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise RuntimeError(f"{context} is missing required columns: {missing}")


def build_company_map(firm_panel_csv: Path) -> Tuple[pd.DataFrame, Dict[str, int]]:
    panel = pd.read_csv(firm_panel_csv, usecols=["companyname", "firm_id"], low_memory=False)
    panel["company_norm"] = panel["companyname"].map(normalize_string)
    panel["firm_id_key"] = normalize_firm_id(panel["firm_id"])
    panel = panel.loc[panel["company_norm"].notna() & panel["firm_id_key"].notna()].copy()
    panel["firm_nonnull"] = panel["firm_id_key"].notna().astype(int)
    panel = panel.sort_values(["company_norm", "firm_nonnull"], ascending=[True, False])
    by_company = panel.groupby("company_norm")["firm_id_key"].nunique(dropna=True)
    n_multi = int((by_company > 1).sum())
    out = panel.drop_duplicates(subset=["company_norm"], keep="first")[["company_norm", "firm_id_key"]]
    return out, {"n_company_norm_unique": int(out["company_norm"].nunique()), "n_company_with_multi_firm_id": n_multi}


def load_role_metadata(candidates_parquet: Path, job_ids: List[str]) -> pd.DataFrame:
    if not job_ids:
        return pd.DataFrame(
            columns=["job_id", "title", "title_cleaned", "role_k150", "role_k50", "role_k7", "company_cleaned", "post_date"]
        )

    cols = ["job_id", "title", "title_cleaned", "role_k150", "role_k50", "role_k7", "company_cleaned", "post_date"]
    df = pd.read_parquet(candidates_parquet, columns=cols)
    df["job_id"] = normalize_job_id(df["job_id"])
    df = df.loc[df["job_id"].isin(set(job_ids))].copy()
    df = df.drop_duplicates(subset=["job_id"], keep="first")
    return df


def software_role_flag(df: pd.DataFrame) -> pd.Series:
    role7 = df.get("role_k7", pd.Series("", index=df.index)).fillna("").astype(str)
    role50 = df.get("role_k50", pd.Series("", index=df.index)).fillna("").astype(str)
    role150 = df.get("role_k150", pd.Series("", index=df.index)).fillna("").astype(str)
    title = df.get("title", pd.Series("", index=df.index)).fillna("").astype(str)
    title_cleaned = df.get("title_cleaned", pd.Series("", index=df.index)).fillna("").astype(str)

    role_hit = (
        role7.str.contains(r"engineer", case=False, regex=True)
        | role50.str.contains(SOFTWARE_ROLE_RE, regex=True)
        | role150.str.contains(SOFTWARE_ROLE_RE, regex=True)
    )
    text_hit = title.str.contains(SOFTWARE_TEXT_RE, regex=True) | title_cleaned.str.contains(SOFTWARE_TEXT_RE, regex=True)
    return (role_hit | text_hit).astype(bool)


def aggregate_llm_panel(
    postings_merge: pd.DataFrame,
    role_meta: pd.DataFrame,
    *,
    company_map: pd.DataFrame,
) -> pd.DataFrame:
    required = ["job_id", "firm_id", "candidate_post_date", "llm_parse_ok", "employee_equity_comp_offered", "equity_context"]
    require_columns(postings_merge, required, context="postings merge CSV")

    work = postings_merge.copy()
    work["job_id"] = normalize_job_id(work["job_id"])
    work["firm_id_key_from_merge"] = normalize_firm_id(work["firm_id"])

    # Resolve onto the current canonical firm-id domain by company name first.
    for source_col in ["companyname_panel", "company_cleaned"]:
        norm_col = f"{source_col}_norm"
        key_col = f"{source_col}_firm_id_key"
        if source_col not in work.columns:
            work[key_col] = pd.NA
            continue
        work[norm_col] = work[source_col].map(normalize_string)
        work = work.merge(
            company_map.rename(columns={"company_norm": norm_col, "firm_id_key": key_col}),
            on=norm_col,
            how="left",
        )

    work["firm_id_key"] = (
        work["companyname_panel_firm_id_key"]
        .combine_first(work["company_cleaned_firm_id_key"])
        .combine_first(work["firm_id_key_from_merge"])
    )
    work["yh"] = add_halfyear_date(work["candidate_post_date"])
    work = work.loc[work["firm_id_key"].notna() & work["yh"].notna()].copy()
    if work.empty:
        return pd.DataFrame()

    if not role_meta.empty:
        role_cols = ["job_id", "title", "title_cleaned", "role_k150", "role_k50", "role_k7"]
        work = work.merge(role_meta[role_cols], on="job_id", how="left")
    else:
        for col in ["title", "title_cleaned", "role_k150", "role_k50", "role_k7"]:
            work[col] = pd.NA

    parse_ok = to_bool(work["llm_parse_ok"]).fillna(False).astype(bool)
    eq_true_raw = to_bool(work["employee_equity_comp_offered"]).fillna(False).astype(bool)
    context = work["equity_context"].fillna("").astype(str).str.lower()
    context_has_employee = context.str.contains("employee_equity_compensation", regex=False)
    eq_true_strict = eq_true_raw & context_has_employee
    is_software_role = software_role_flag(work)

    work["parse_ok_int"] = parse_ok.astype(int)
    work["eq_true_raw_parse_int"] = (parse_ok & eq_true_raw).astype(int)
    work["eq_true_strict_parse_int"] = (parse_ok & eq_true_strict).astype(int)
    work["software_role_int"] = is_software_role.astype(int)
    work["parse_ok_software_int"] = (parse_ok & is_software_role).astype(int)
    work["eq_true_raw_software_parse_int"] = (parse_ok & is_software_role & eq_true_raw).astype(int)
    work["eq_true_strict_software_parse_int"] = (parse_ok & is_software_role & eq_true_strict).astype(int)

    agg = (
        work.groupby(["firm_id_key", "yh"], dropna=False)
        .agg(
            n_llm_target_postings=("job_id", "size"),
            llm_n_parse_ok_raw=("parse_ok_int", "sum"),
            llm_n_equity_true_raw=("eq_true_raw_parse_int", "sum"),
            llm_n_equity_true_strict=("eq_true_strict_parse_int", "sum"),
            n_llm_target_postings_software=("software_role_int", "sum"),
            llm_n_parse_ok_software=("parse_ok_software_int", "sum"),
            llm_n_equity_true_software_raw=("eq_true_raw_software_parse_int", "sum"),
            llm_n_equity_true_software_strict=("eq_true_strict_software_parse_int", "sum"),
        )
        .reset_index()
    )

    def add_metrics(
        frame: pd.DataFrame,
        *,
        num_col: str,
        den_col: str,
        prefix: str,
    ) -> None:
        frame[f"llm_equity_share_parse_ok_{prefix}"] = frame[num_col] / frame[den_col].where(frame[den_col] > 0)
        frame[f"llm_equity_any_{prefix}"] = np.where(
            frame[den_col] > 0,
            (frame[num_col] > 0).astype(int),
            np.nan,
        )
        frame[f"llm_equity_count_parse_ok_{prefix}"] = np.where(frame[den_col] > 0, frame[num_col], np.nan)

    add_metrics(agg, num_col="llm_n_equity_true_raw", den_col="llm_n_parse_ok_raw", prefix="raw")
    add_metrics(agg, num_col="llm_n_equity_true_strict", den_col="llm_n_parse_ok_raw", prefix="strict")
    add_metrics(
        agg,
        num_col="llm_n_equity_true_software_raw",
        den_col="llm_n_parse_ok_software",
        prefix="software_raw",
    )
    add_metrics(
        agg,
        num_col="llm_n_equity_true_software_strict",
        den_col="llm_n_parse_ok_software",
        prefix="software_strict",
    )

    return agg


def aggregate_postings_counts_from_glob(*, input_glob: str, company_map: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        input_q = sql_quote_literal(Path(input_glob).as_posix())
        query = f"""
        WITH src AS (
          SELECT
            lower(trim(coalesce(company_cleaned, ''))) AS company_norm,
            coalesce(
              try_strptime(cast(post_date as varchar), '%Y-%m-%d'),
              try_strptime(cast(post_date as varchar), '%Y-%m-%d %H:%M:%S')
            ) AS dt
          FROM read_csv_auto({input_q}, SAMPLE_SIZE=20000)
          WHERE length(coalesce(description, '')) > 0
        )
        SELECT
          company_norm,
          strftime(
            CASE
              WHEN month(dt) <= 6 THEN make_date(year(dt), 1, 1)
              ELSE make_date(year(dt), 7, 1)
            END,
            '%Y-%m-%d'
          ) AS yh,
          count(*) AS n_postings_desc_total
        FROM src
        WHERE company_norm <> '' AND dt IS NOT NULL
        GROUP BY 1, 2
        """
        counts = con.execute(query).fetchdf()
    finally:
        con.close()

    merged = counts.merge(company_map, on="company_norm", how="left")
    merged = merged.loc[merged["firm_id_key"].notna()].copy()
    out = (
        merged.groupby(["firm_id_key", "yh"], dropna=False)["n_postings_desc_total"]
        .sum()
        .reset_index()
    )
    return out


def aggregate_keyword_hits_from_candidates(*, candidates_parquet: Path, company_map: pd.DataFrame) -> pd.DataFrame:
    con = duckdb.connect()
    try:
        pq = sql_quote_literal(candidates_parquet.as_posix())
        query = f"""
        WITH src AS (
          SELECT
            lower(trim(coalesce(company_cleaned, ''))) AS company_norm,
            coalesce(
              try_strptime(cast(post_date as varchar), '%Y-%m-%d'),
              try_strptime(cast(post_date as varchar), '%Y-%m-%d %H:%M:%S')
            ) AS dt
          FROM parquet_scan({pq})
        )
        SELECT
          company_norm,
          strftime(
            CASE
              WHEN month(dt) <= 6 THEN make_date(year(dt), 1, 1)
              ELSE make_date(year(dt), 7, 1)
            END,
            '%Y-%m-%d'
          ) AS yh,
          count(*) AS n_keyword_hit_candidates
        FROM src
        WHERE company_norm <> '' AND dt IS NOT NULL
        GROUP BY 1, 2
        """
        hits = con.execute(query).fetchdf()
    finally:
        con.close()

    merged = hits.merge(company_map, on="company_norm", how="left")
    merged = merged.loc[merged["firm_id_key"].notna()].copy()
    out = (
        merged.groupby(["firm_id_key", "yh"], dropna=False)["n_keyword_hit_candidates"]
        .sum()
        .reset_index()
    )
    return out


def add_firm_level_bins(panel: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, float]]:
    thresholds: Dict[str, float] = {}
    frame = panel.copy()

    metric_cols = {
        "raw_share": "llm_equity_share_parse_ok_raw",
        "raw_count": "llm_equity_count_parse_ok_raw",
        "strict_share": "llm_equity_share_parse_ok_strict",
        "strict_count": "llm_equity_count_parse_ok_strict",
        "software_strict_share": "llm_equity_share_parse_ok_software_strict",
        "software_strict_count": "llm_equity_count_parse_ok_software_strict",
    }

    for label, col in metric_cols.items():
        if col not in frame.columns:
            continue
        firm_mean = (
            frame.groupby("firm_id_key", dropna=False)[col]
            .mean()
            .rename(f"firm_mean_{label}_obs")
            .reset_index()
        )
        frame = frame.merge(firm_mean, on="firm_id_key", how="left")

        mean_col = f"firm_mean_{label}_obs"
        valid = frame[[mean_col]].dropna()
        if valid.empty:
            for suffix in ["ge_median_obs", "top_quartile_obs", "top_quintile_obs"]:
                frame[f"firm_{label}_{suffix}"] = np.nan
            continue

        q50 = float(valid[mean_col].quantile(0.50))
        q75 = float(valid[mean_col].quantile(0.75))
        q80 = float(valid[mean_col].quantile(0.80))
        thresholds[f"{label}_q50"] = q50
        thresholds[f"{label}_q75"] = q75
        thresholds[f"{label}_q80"] = q80

        frame[f"firm_{label}_ge_median_obs"] = np.where(frame[mean_col].notna(), (frame[mean_col] >= q50).astype(int), np.nan)
        frame[f"firm_{label}_top_quartile_obs"] = np.where(
            frame[mean_col].notna(), (frame[mean_col] >= q75).astype(int), np.nan
        )
        frame[f"firm_{label}_top_quintile_obs"] = np.where(
            frame[mean_col].notna(), (frame[mean_col] >= q80).astype(int), np.nan
        )

    return frame, thresholds


def build_status_columns(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out["status_observed_positive"] = (
        (out["llm_n_parse_ok_raw"] > 0) & (out["llm_n_equity_true_raw"] > 0)
    ).astype(int)
    out["status_observed_true_zero"] = (
        (out["llm_n_parse_ok_raw"] > 0) & (out["llm_n_equity_true_raw"] == 0)
    ).astype(int)
    out["status_backfill_keyword_unparsed"] = (
        (out["llm_n_parse_ok_raw"] == 0) & (out["n_keyword_hit_candidates"] > 0)
    ).astype(int)
    out["status_backfill_no_keyword_hit"] = (
        (out["n_keyword_hit_candidates"] == 0) & (out["n_postings_desc_total"] > 0)
    ).astype(int)
    out["status_backfill_no_postings"] = (out["n_postings_desc_total"] == 0).astype(int)

    out["status_name"] = np.select(
        [
            out["status_observed_positive"] == 1,
            out["status_observed_true_zero"] == 1,
            out["status_backfill_keyword_unparsed"] == 1,
            out["status_backfill_no_keyword_hit"] == 1,
            out["status_backfill_no_postings"] == 1,
        ],
        [
            "observed_positive",
            "observed_true_zero",
            "backfill_keyword_unparsed",
            "backfill_no_keyword_hit",
            "backfill_no_postings",
        ],
        default="other",
    )

    out["eq_has_parse"] = (out["llm_n_parse_ok_raw"] > 0).astype(int)
    out["eq_missing_parse"] = (out["llm_n_parse_ok_raw"] == 0).astype(int)
    out["eq_missing_keyword_hit"] = (out["n_keyword_hit_candidates"] == 0).astype(int)
    out["eq_missing_postings"] = (out["n_postings_desc_total"] == 0).astype(int)
    return out


def summarize_status(panel: pd.DataFrame) -> pd.DataFrame:
    summary = (
        panel.groupby("status_name", dropna=False)
        .agg(
            n_firm_yh_rows=("firm_id_key", "size"),
            n_firms=("firm_id_key", "nunique"),
        )
        .reset_index()
        .sort_values("n_firm_yh_rows", ascending=False)
    )
    total = float(summary["n_firm_yh_rows"].sum()) if not summary.empty else 0.0
    summary["share_firm_yh_rows"] = summary["n_firm_yh_rows"] / total if total > 0 else np.nan
    return summary


def summarize_status_by_startup(panel: pd.DataFrame) -> pd.DataFrame:
    summary = (
        panel.groupby(["status_name", "startup"], dropna=False)
        .agg(
            n_firm_yh_rows=("firm_id_key", "size"),
            n_firms=("firm_id_key", "nunique"),
        )
        .reset_index()
        .sort_values(["status_name", "startup"])
    )
    return summary


def main() -> None:
    args = parse_args()

    postings_merge_csv = args.postings_merge_csv.expanduser().resolve()
    candidates_parquet = args.candidates_parquet.expanduser().resolve()
    firm_panel_csv = args.firm_panel_csv.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()

    require_file(postings_merge_csv, nonempty=True, purpose="posting-level LLM merge CSV")
    require_file(candidates_parquet, nonempty=True, purpose="equity candidates parquet")
    require_file(firm_panel_csv, nonempty=True, purpose="firm panel with CB CSV")
    ensure_dir(out_dir)

    postings_merge = pd.read_csv(postings_merge_csv, low_memory=False)
    postings_merge["job_id"] = normalize_job_id(postings_merge["job_id"])
    job_ids = [j for j in postings_merge["job_id"].dropna().astype(str).tolist() if j]

    role_meta = load_role_metadata(candidates_parquet, job_ids)
    company_map, map_diag = build_company_map(firm_panel_csv)
    llm_panel = aggregate_llm_panel(postings_merge, role_meta, company_map=company_map)
    postings_counts = aggregate_postings_counts_from_glob(input_glob=args.input_glob, company_map=company_map)
    keyword_hits = aggregate_keyword_hits_from_candidates(candidates_parquet=candidates_parquet, company_map=company_map)

    universe = pd.read_csv(firm_panel_csv, low_memory=False)
    require_columns(universe, ["firm_id", "yh"], context="firm panel CSV")
    keep_cols = [c for c in ["firm_id", "yh", "companyname", "startup", "public", "org_uuid", "industry", "hqstate"] if c in universe.columns]
    universe = universe[keep_cols].copy()
    universe["firm_id_key"] = normalize_firm_id(universe["firm_id"])
    universe["yh"] = add_halfyear_date(universe["yh"])
    universe = universe.loc[universe["firm_id_key"].notna() & universe["yh"].notna()].copy()
    universe = universe.drop_duplicates(subset=["firm_id_key", "yh"], keep="first")

    panel = universe.merge(llm_panel, on=["firm_id_key", "yh"], how="left")
    panel = panel.merge(postings_counts, on=["firm_id_key", "yh"], how="left")
    panel = panel.merge(keyword_hits, on=["firm_id_key", "yh"], how="left")

    count_cols = [
        "n_llm_target_postings",
        "llm_n_parse_ok_raw",
        "llm_n_equity_true_raw",
        "llm_n_equity_true_strict",
        "n_llm_target_postings_software",
        "llm_n_parse_ok_software",
        "llm_n_equity_true_software_raw",
        "llm_n_equity_true_software_strict",
        "n_postings_desc_total",
        "n_keyword_hit_candidates",
    ]
    for col in count_cols:
        if col not in panel.columns:
            panel[col] = 0
        panel[col] = pd.to_numeric(panel[col], errors="coerce").fillna(0).astype(int)

    # Recompute metric columns after merge/fill to ensure consistency.
    def recompute_metrics(df: pd.DataFrame, num: str, den: str, prefix: str) -> None:
        df[f"llm_equity_share_parse_ok_{prefix}"] = df[num] / df[den].where(df[den] > 0)
        df[f"llm_equity_any_{prefix}"] = np.where(df[den] > 0, (df[num] > 0).astype(int), np.nan)
        df[f"llm_equity_count_parse_ok_{prefix}"] = np.where(df[den] > 0, df[num], np.nan)

    recompute_metrics(panel, "llm_n_equity_true_raw", "llm_n_parse_ok_raw", "raw")
    recompute_metrics(panel, "llm_n_equity_true_strict", "llm_n_parse_ok_raw", "strict")
    recompute_metrics(panel, "llm_n_equity_true_software_raw", "llm_n_parse_ok_software", "software_raw")
    recompute_metrics(panel, "llm_n_equity_true_software_strict", "llm_n_parse_ok_software", "software_strict")

    panel = build_status_columns(panel)
    panel, thresholds = add_firm_level_bins(panel)

    status_summary = summarize_status(panel)
    status_by_startup = summarize_status_by_startup(panel)

    run_label = args.run_label.strip() or "enriched_equity"
    panel_path = out_dir / f"{run_label}_firm_yh_llm_equity_enriched.csv"
    summary_path = out_dir / f"{run_label}_llm_equity_backfill_audit_summary.csv"
    startup_summary_path = out_dir / f"{run_label}_llm_equity_backfill_audit_by_startup.csv"
    meta_path = out_dir / f"{run_label}_llm_equity_enriched_summary.json"

    panel.to_csv(panel_path, index=False)
    status_summary.to_csv(summary_path, index=False)
    status_by_startup.to_csv(startup_summary_path, index=False)

    meta = {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {
            "postings_merge_csv": str(postings_merge_csv),
            "candidates_parquet": str(candidates_parquet),
            "firm_panel_csv": str(firm_panel_csv),
            "input_glob": args.input_glob,
        },
        "rows": {
            "panel_rows": int(len(panel)),
            "unique_firms": int(panel["firm_id_key"].nunique()),
            "rows_with_parse_ok": int((panel["llm_n_parse_ok_raw"] > 0).sum()),
            "rows_with_keyword_hits": int((panel["n_keyword_hit_candidates"] > 0).sum()),
            "rows_with_any_postings": int((panel["n_postings_desc_total"] > 0).sum()),
        },
        "status_counts": {
            row["status_name"]: int(row["n_firm_yh_rows"]) for _, row in status_summary.iterrows()
        },
        "firm_map_diagnostics": map_diag,
        "bin_thresholds": thresholds,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    latest_panel = out_dir / "latest_firm_yh_llm_equity_enriched.csv"
    latest_summary = out_dir / "latest_llm_equity_backfill_audit_summary.csv"
    latest_startup_summary = out_dir / "latest_llm_equity_backfill_audit_by_startup.csv"
    latest_meta = out_dir / "latest_llm_equity_enriched_summary.json"

    panel.to_csv(latest_panel, index=False)
    status_summary.to_csv(latest_summary, index=False)
    status_by_startup.to_csv(latest_startup_summary, index=False)
    latest_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print("Wrote enriched panel:", panel_path)
    print("Wrote status summary:", summary_path)
    print("Wrote status by startup:", startup_summary_path)
    print("Wrote metadata summary:", meta_path)


if __name__ == "__main__":
    main()
