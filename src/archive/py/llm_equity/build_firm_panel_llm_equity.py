#!/usr/bin/env python3
"""Build firm×half-year LLM-equity measures and merge into the firm panel.

Inputs
------
- posting-level merged LLM file from `merge_llm_equity_with_firm_panel.py`
- `data/clean/firm_panel_with_cb.csv`

Outputs
-------
- firm×yh LLM equity panel (aggregated from postings)
- firm panel with LLM equity columns merged on (`firm_id`, `yh`)
- summary JSON with coverage metrics
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.py.project_paths import DATA_CLEAN, RESULTS_RAW, ensure_dir, require_file


INSTRUMENT_KEYS = [
    "stock_options",
    "rsu",
    "restricted_stock",
    "espp",
    "esop",
    "phantom_equity",
    "profit_interest",
    "carried_interest",
    "stock_appreciation_rights",
    "other_equity",
]

POSTINGS_MERGE_DEFAULT = RESULTS_RAW / "postings_description_equity" / "firm_merge" / "latest_postings_llm_firm_merge.csv"
FIRM_PANEL_DEFAULT = DATA_CLEAN / "firm_panel_with_cb.csv"
OUT_DIR_DEFAULT = RESULTS_RAW / "postings_description_equity" / "firm_merge"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--postings-merge-csv",
        type=Path,
        default=POSTINGS_MERGE_DEFAULT,
        help=f"Posting-level merged file (default: {POSTINGS_MERGE_DEFAULT}).",
    )
    parser.add_argument(
        "--firm-panel-csv",
        type=Path,
        default=FIRM_PANEL_DEFAULT,
        help=f"Firm panel CSV (default: {FIRM_PANEL_DEFAULT}).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR_DEFAULT,
        help=f"Directory for outputs (default: {OUT_DIR_DEFAULT}).",
    )
    parser.add_argument(
        "--run-label",
        type=str,
        default="",
        help="Optional output prefix (default: inferred from postings filename).",
    )
    return parser.parse_args()


def to_boolean(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    out = pd.Series(pd.NA, index=series.index, dtype="boolean")
    out.loc[s.isin(["true", "1", "t", "yes"])] = True
    out.loc[s.isin(["false", "0", "f", "no"])] = False
    return out


def add_halfyear_date(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    months = np.where(dt.dt.month <= 6, 1, 7)
    yh_dt = pd.to_datetime(
        {"year": dt.dt.year, "month": months, "day": 1},
        errors="coerce",
    )
    return yh_dt.dt.strftime("%Y-%m-%d")


def normalize_firm_id(series: pd.Series) -> pd.Series:
    out = series.astype(str).str.strip()
    out = out.where(out.ne(""), other=pd.NA)
    out = out.where(~out.str.lower().isin(["nan", "none"]), other=pd.NA)
    return out.str.lower()


def build_firm_yh_panel(postings: pd.DataFrame) -> pd.DataFrame:
    work = postings.copy()

    if "candidate_post_date" not in work.columns:
        raise RuntimeError("postings merge file is missing `candidate_post_date`.")
    if "firm_id" not in work.columns:
        raise RuntimeError("postings merge file is missing `firm_id`.")

    work["firm_id_key"] = normalize_firm_id(work["firm_id"])
    work["yh"] = add_halfyear_date(work["candidate_post_date"])

    work = work.loc[work["firm_id_key"].notna() & work["yh"].notna()].copy()
    if work.empty:
        return pd.DataFrame()

    work["llm_parse_ok_bool"] = to_boolean(work.get("llm_parse_ok", pd.Series(False, index=work.index)))
    work["llm_has_output_bool"] = to_boolean(work.get("llm_has_output", pd.Series(False, index=work.index)))
    work["equity_offered_bool"] = to_boolean(work.get("employee_equity_comp_offered", pd.Series(pd.NA, index=work.index)))

    work["llm_parse_ok_int"] = work["llm_parse_ok_bool"].fillna(False).astype(int)
    work["llm_has_output_int"] = work["llm_has_output_bool"].fillna(False).astype(int)
    work["equity_true_int"] = (work["equity_offered_bool"] == True).fillna(False).astype(int)
    work["equity_false_int"] = (work["equity_offered_bool"] == False).fillna(False).astype(int)

    for key in INSTRUMENT_KEYS:
        src = f"instrument_{key}_mentioned"
        if src in work.columns:
            work[f"{src}_bool"] = to_boolean(work[src])
        else:
            work[f"{src}_bool"] = pd.Series(pd.NA, index=work.index, dtype="boolean")
        work[f"{src}_int"] = (work[f"{src}_bool"] == True).fillna(False).astype(int)

    group_cols = ["firm_id_key", "yh"]
    static_cols = [c for c in ["companyname_panel", "org_uuid", "public", "startup", "remote", "teleworkable", "age", "industry", "hqstate"] if c in work.columns]

    agg = (
        work.groupby(group_cols, dropna=False)
        .agg(
            llm_n_target_postings=("custom_id", "size"),
            llm_n_with_output=("llm_has_output_int", "sum"),
            llm_n_parse_ok=("llm_parse_ok_int", "sum"),
            llm_n_equity_true=("equity_true_int", "sum"),
            llm_n_equity_false=("equity_false_int", "sum"),
        )
        .reset_index()
    )

    for key in INSTRUMENT_KEYS:
        src = f"instrument_{key}_mentioned_int"
        dst = f"llm_n_{key}_mentioned"
        counts = work.groupby(group_cols, dropna=False)[src].sum().reset_index(name=dst)
        agg = agg.merge(counts, on=group_cols, how="left")

    if static_cols:
        static = work[group_cols + static_cols].drop_duplicates(subset=group_cols)
        agg = agg.merge(static, on=group_cols, how="left")

    agg["llm_equity_share_parse_ok"] = agg["llm_n_equity_true"] / agg["llm_n_parse_ok"].where(agg["llm_n_parse_ok"] > 0)
    agg["llm_equity_any"] = np.where(agg["llm_n_parse_ok"] > 0, (agg["llm_n_equity_true"] > 0).astype(int), np.nan)
    return agg.sort_values(["llm_n_parse_ok", "llm_n_target_postings"], ascending=[False, False])


def merge_with_firm_panel(firm_panel_csv: Path, llm_panel: pd.DataFrame) -> pd.DataFrame:
    panel = pd.read_csv(firm_panel_csv, low_memory=False)
    if "firm_id" not in panel.columns or "yh" not in panel.columns:
        raise RuntimeError(f"{firm_panel_csv} must include `firm_id` and `yh`.")

    panel["firm_id_key"] = normalize_firm_id(panel["firm_id"])
    panel["yh"] = pd.to_datetime(panel["yh"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = panel.merge(llm_panel, on=["firm_id_key", "yh"], how="left", suffixes=("", "_llm"))
    return merged


def build_summary(llm_panel: pd.DataFrame, merged_panel: pd.DataFrame) -> Dict[str, Any]:
    n_firm_yh = int(len(llm_panel))
    n_firm_yh_parse_ok = int((llm_panel["llm_n_parse_ok"] > 0).sum()) if not llm_panel.empty else 0
    n_firms = int(llm_panel["firm_id_key"].nunique()) if not llm_panel.empty else 0
    n_panel_rows = int(len(merged_panel))
    n_panel_rows_with_llm = int(merged_panel["llm_n_parse_ok"].notna().sum()) if "llm_n_parse_ok" in merged_panel.columns else 0

    return {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "firm_yh_rows_in_llm_panel": n_firm_yh,
        "firm_yh_rows_with_parse_ok": n_firm_yh_parse_ok,
        "firms_with_any_llm_row": n_firms,
        "merged_firm_panel_rows": n_panel_rows,
        "merged_firm_panel_rows_with_llm_data": n_panel_rows_with_llm,
        "llm_merge_rate_in_firm_panel_rows": (n_panel_rows_with_llm / n_panel_rows) if n_panel_rows > 0 else None,
    }


def main() -> None:
    args = parse_args()

    postings_merge_csv = args.postings_merge_csv.expanduser().resolve()
    firm_panel_csv = args.firm_panel_csv.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()

    require_file(postings_merge_csv, nonempty=True, purpose="posting-level LLM merge CSV")
    require_file(firm_panel_csv, nonempty=True, purpose="firm panel CSV")
    ensure_dir(out_dir)

    postings = pd.read_csv(postings_merge_csv, low_memory=False)
    llm_panel = build_firm_yh_panel(postings)
    merged_panel = merge_with_firm_panel(firm_panel_csv, llm_panel)
    summary = build_summary(llm_panel, merged_panel)

    base = args.run_label.strip()
    if not base:
        name = postings_merge_csv.stem
        suffix = "_postings_llm_firm_merge"
        base = name[:-len(suffix)] if name.endswith(suffix) else name

    llm_panel_path = out_dir / f"{base}_firm_yh_llm_equity.csv"
    merged_path = out_dir / f"{base}_firm_panel_with_cb_llm_equity.csv"
    summary_path = out_dir / f"{base}_firm_panel_llm_summary.json"

    llm_panel.to_csv(llm_panel_path, index=False)
    merged_panel.to_csv(merged_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    latest_llm_panel = out_dir / "latest_firm_yh_llm_equity.csv"
    latest_merged = out_dir / "latest_firm_panel_with_cb_llm_equity.csv"
    latest_summary = out_dir / "latest_firm_panel_llm_summary.json"
    llm_panel.to_csv(latest_llm_panel, index=False)
    merged_panel.to_csv(latest_merged, index=False)
    latest_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("Wrote firm×yh LLM panel:", llm_panel_path)
    print("Wrote merged firm panel:", merged_path)
    print("Wrote summary:", summary_path)
    print("Summary stats:", summary)


if __name__ == "__main__":
    main()
