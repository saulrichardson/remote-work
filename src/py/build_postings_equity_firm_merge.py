#!/usr/bin/env python3
"""Merge LLM equity-extraction outputs back to firm-level identifiers.

This script links a Batch-API run to firm metadata by:
1) reading request metadata from `batch_*.jsonl` files (custom_id, job_id, company_cleaned),
2) reading downloaded LLM outputs from `*_output.jsonl`,
3) merging onto `data/clean/firm_panel_with_cb.csv` using normalized company names.

Outputs
-------
- posting-level merged CSV
- firm-level aggregated CSV
- unmatched-company diagnostics CSV
- merge summary JSON
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.py.project_paths import DATA_CLEAN, RESULTS_RAW, ensure_dir, require_file

try:
    import duckdb  # type: ignore
except ModuleNotFoundError:
    duckdb = None


JOB_ID_FROM_CUSTOM_ID_RE = re.compile(r"__job_(\d+)$")
JOB_ID_FROM_PROMPT_RE = re.compile(r"(?mi)^job_id:\s*([^\n\r]+)\s*$")
COMPANY_FROM_PROMPT_RE = re.compile(r"(?mi)^company_cleaned:\s*([^\n\r]*)\s*$")

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

FIRM_PANEL_DEFAULT = DATA_CLEAN / "firm_panel_with_cb.csv"
EQUITY_CANDIDATES_DEFAULT = RESULTS_RAW / "postings_description_equity" / "equity_candidates.parquet"
OUT_DIR_DEFAULT = RESULTS_RAW / "postings_description_equity" / "firm_merge"


@dataclass(frozen=True)
class FirmMapDiagnostics:
    n_rows_read: int
    n_company_norm_unique: int
    n_company_with_multiple_firm_ids: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-input-dir", type=Path, required=True, help="Run folder containing batch_*.jsonl files.")
    parser.add_argument(
        "--run-output-dir",
        type=Path,
        action="append",
        required=True,
        help="Run folder containing *_output.jsonl files. Repeatable.",
    )
    parser.add_argument(
        "--firm-panel-csv",
        type=Path,
        default=FIRM_PANEL_DEFAULT,
        help=f"Firm panel CSV with firm identifiers (default: {FIRM_PANEL_DEFAULT}).",
    )
    parser.add_argument(
        "--candidates-parquet",
        type=Path,
        default=EQUITY_CANDIDATES_DEFAULT,
        help=(
            "Optional equity_candidates.parquet for extra job-level metadata "
            f"(default: {EQUITY_CANDIDATES_DEFAULT})."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR_DEFAULT,
        help=f"Directory for merged outputs (default: {OUT_DIR_DEFAULT}).",
    )
    parser.add_argument(
        "--run-label",
        type=str,
        default="",
        help="Optional label prefix for output files (default: input-dir folder name).",
    )
    return parser.parse_args()


def normalize_company(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text == "nan":
        return None
    return text


def extract_user_prompt_text(body: Dict[str, Any]) -> str:
    messages = body.get("input")
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
    return ""


def parse_job_id(custom_id: str, user_prompt: str) -> Optional[str]:
    match = JOB_ID_FROM_CUSTOM_ID_RE.search(custom_id)
    if match:
        return match.group(1)
    match = JOB_ID_FROM_PROMPT_RE.search(user_prompt)
    if match:
        value = match.group(1).strip()
        return value if value else None
    return None


def parse_company_cleaned(user_prompt: str) -> Optional[str]:
    match = COMPANY_FROM_PROMPT_RE.search(user_prompt)
    if not match:
        return None
    value = match.group(1).strip()
    return value if value else None


def load_input_requests(run_input_dir: Path) -> pd.DataFrame:
    rows: Dict[str, Dict[str, Any]] = {}
    batch_files = sorted(run_input_dir.glob("batch_*.jsonl"))
    if not batch_files:
        raise RuntimeError(f"No batch_*.jsonl files found in {run_input_dir}")

    for path in batch_files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                custom_id = payload.get("custom_id")
                if not isinstance(custom_id, str) or not custom_id:
                    continue
                if custom_id in rows:
                    continue
                body = payload.get("body")
                if not isinstance(body, dict):
                    body = {}
                user_prompt = extract_user_prompt_text(body)
                rows[custom_id] = {
                    "custom_id": custom_id,
                    "job_id": parse_job_id(custom_id, user_prompt),
                    "company_cleaned": parse_company_cleaned(user_prompt),
                }

    frame = pd.DataFrame(rows.values())
    if frame.empty:
        raise RuntimeError(f"Parsed 0 request rows from {run_input_dir}")
    frame["company_cleaned_norm"] = frame["company_cleaned"].map(normalize_company)
    return frame


def load_candidate_metadata(candidates_parquet: Path, job_ids: List[str]) -> pd.DataFrame:
    if not candidates_parquet.exists() or not job_ids:
        return pd.DataFrame(columns=["job_id"])
    if duckdb is None:
        return pd.DataFrame(columns=["job_id"])

    ids_df = pd.DataFrame({"job_id": pd.Series(job_ids, dtype="string")}).drop_duplicates(subset=["job_id"])
    if ids_df.empty:
        return pd.DataFrame(columns=["job_id"])

    con = duckdb.connect()
    try:
        con.register("target_job_ids", ids_df)
        query = f"""
        SELECT
          CAST(c.job_id AS VARCHAR) AS job_id,
          c.company_cleaned AS candidate_company_cleaned,
          c.company AS candidate_company_raw,
          c.post_date AS candidate_post_date,
          c.gvkey AS candidate_gvkey,
          c.factset_entity_id AS candidate_factset_entity_id,
          c.state AS candidate_state,
          c.industry_cleaned AS candidate_industry
        FROM parquet_scan('{candidates_parquet.as_posix()}') AS c
        INNER JOIN target_job_ids AS t
          ON CAST(c.job_id AS VARCHAR) = t.job_id
        """
        frame = con.execute(query).fetchdf()
    finally:
        con.close()

    if frame.empty:
        return frame
    frame = frame.sort_values("job_id").drop_duplicates(subset=["job_id"], keep="first")
    frame["candidate_company_cleaned_norm"] = frame["candidate_company_cleaned"].map(normalize_company)
    frame["candidate_gvkey_num"] = pd.to_numeric(frame["candidate_gvkey"], errors="coerce")
    return frame


def extract_output_text(payload: Dict[str, Any]) -> Optional[str]:
    response = payload.get("response")
    if not isinstance(response, dict):
        return None
    body = response.get("body")
    if not isinstance(body, dict):
        return None
    output_items = body.get("output")
    if not isinstance(output_items, list):
        return None
    for item in output_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content_items = item.get("content")
        if not isinstance(content_items, list):
            continue
        for content in content_items:
            if not isinstance(content, dict):
                continue
            if content.get("type") != "output_text":
                continue
            text = content.get("text")
            if isinstance(text, str):
                return text
    return None


def score_output_record(record: Dict[str, Any]) -> Tuple[int, int]:
    parse_ok = 1 if record.get("llm_parse_ok") else 0
    has_output = 1 if record.get("llm_has_output") else 0
    return parse_ok, has_output


def flatten_extraction(extraction: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["output_job_id"] = extraction.get("job_id")
    out["employee_equity_comp_offered"] = extraction.get("employee_equity_comp_offered")
    contexts = extraction.get("equity_context")
    if isinstance(contexts, list):
        out["equity_context"] = "|".join(str(x) for x in contexts if x is not None)
    else:
        out["equity_context"] = None
    instruments = extraction.get("equity_instruments")
    for key in INSTRUMENT_KEYS:
        col = f"instrument_{key}_mentioned"
        mentioned = None
        if isinstance(instruments, dict):
            item = instruments.get(key)
            if isinstance(item, dict):
                val = item.get("mentioned")
                if isinstance(val, bool):
                    mentioned = val
        out[col] = mentioned
    return out


def load_output_records(run_output_dir: Path) -> pd.DataFrame:
    by_custom_id: Dict[str, Dict[str, Any]] = {}
    output_files = sorted(run_output_dir.glob("*_output.jsonl"))

    for path in output_files:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                custom_id = payload.get("custom_id")
                if not isinstance(custom_id, str) or not custom_id:
                    continue

                output_text = extract_output_text(payload)
                parse_ok = False
                extraction_obj: Optional[Dict[str, Any]] = None
                flattened: Dict[str, Any] = {}
                if output_text:
                    try:
                        parsed = json.loads(output_text)
                        if isinstance(parsed, dict):
                            parse_ok = True
                            extraction_obj = parsed
                            flattened = flatten_extraction(parsed)
                    except json.JSONDecodeError:
                        parse_ok = False

                record: Dict[str, Any] = {
                    "custom_id": custom_id,
                    "llm_has_output": bool(output_text),
                    "llm_parse_ok": parse_ok,
                    "llm_output_text": output_text,
                    "llm_extraction_json": json.dumps(extraction_obj, ensure_ascii=False) if extraction_obj else None,
                    "llm_response_error": json.dumps(payload.get("error"), ensure_ascii=False),
                    "llm_output_file": path.name,
                    "llm_output_dir": path.parent.name,
                }
                record.update(flattened)

                current = by_custom_id.get(custom_id)
                if current is None or score_output_record(record) >= score_output_record(current):
                    by_custom_id[custom_id] = record

    if not by_custom_id:
        return pd.DataFrame(columns=["custom_id"])
    return pd.DataFrame(by_custom_id.values())


def build_firm_maps(firm_panel_csv: Path) -> Tuple[pd.DataFrame, pd.DataFrame, FirmMapDiagnostics]:
    header = pd.read_csv(firm_panel_csv, nrows=0)
    desired = [
        "companyname",
        "firm_id",
        "org_uuid",
        "public",
        "startup",
        "remote",
        "teleworkable",
        "age",
        "industry",
        "hqstate",
        "gvkey",
    ]
    usecols = [c for c in desired if c in header.columns]
    if "companyname" not in usecols:
        raise RuntimeError(f"{firm_panel_csv} is missing required column: companyname")
    if "firm_id" not in usecols:
        raise RuntimeError(f"{firm_panel_csv} is missing required column: firm_id")

    panel = pd.read_csv(firm_panel_csv, usecols=usecols, low_memory=False)
    panel["company_norm"] = panel["companyname"].map(normalize_company)
    panel = panel.loc[panel["company_norm"].notna()].copy()

    firm_id_numeric = pd.to_numeric(panel["firm_id"], errors="coerce")
    panel["firm_id_nonnull"] = firm_id_numeric.notna().astype(int)
    panel = panel.sort_values(["company_norm", "firm_id_nonnull"], ascending=[True, False])

    company_map = panel.drop_duplicates(subset=["company_norm"], keep="first").copy()
    company_map = company_map.rename(columns={"companyname": "companyname_panel"})
    company_map["gvkey_num"] = pd.to_numeric(company_map.get("gvkey"), errors="coerce")
    company_map = company_map.drop(columns=["firm_id_nonnull"])

    gvkey_map = panel.copy()
    gvkey_map["gvkey_num"] = pd.to_numeric(gvkey_map.get("gvkey"), errors="coerce")
    gvkey_map = gvkey_map.loc[gvkey_map["gvkey_num"].notna()].copy()
    gvkey_map = gvkey_map.rename(columns={"companyname": "companyname_panel"})
    gvkey_map = gvkey_map.sort_values(["gvkey_num", "firm_id_nonnull"], ascending=[True, False])
    gvkey_map = gvkey_map.drop_duplicates(subset=["gvkey_num"], keep="first")
    gvkey_map = gvkey_map.drop(columns=["firm_id_nonnull", "company_norm"])

    by_company = panel.loc[panel["firm_id_nonnull"] == 1].groupby("company_norm")["firm_id"].nunique(dropna=True)
    n_multi = int((by_company > 1).sum())
    diagnostics = FirmMapDiagnostics(
        n_rows_read=int(len(panel)),
        n_company_norm_unique=int(company_map["company_norm"].nunique()),
        n_company_with_multiple_firm_ids=n_multi,
    )
    return company_map, gvkey_map, diagnostics


def aggregate_firm_level(postings: pd.DataFrame) -> pd.DataFrame:
    matched = postings.loc[postings["firm_id"].notna()].copy()
    if matched.empty:
        return pd.DataFrame()

    matched["llm_has_output_int"] = matched["llm_has_output"].fillna(False).astype(int)
    matched["llm_parse_ok_int"] = matched["llm_parse_ok"].fillna(False).astype(int)
    matched["equity_true_int"] = (matched["employee_equity_comp_offered"] == True).astype(int)
    matched["equity_false_int"] = (matched["employee_equity_comp_offered"] == False).astype(int)

    for key in INSTRUMENT_KEYS:
        col = f"instrument_{key}_mentioned"
        matched[f"{col}_int"] = (matched[col] == True).astype(int)

    group_cols = ["firm_id", "companyname_panel"]
    static_cols = [c for c in ["org_uuid", "public", "startup", "remote", "teleworkable", "age", "industry", "hqstate"] if c in matched.columns]

    agg = (
        matched.groupby(group_cols, dropna=False)
        .agg(
            n_target_postings=("custom_id", "size"),
            n_with_output=("llm_has_output_int", "sum"),
            n_parse_ok=("llm_parse_ok_int", "sum"),
            n_equity_true=("equity_true_int", "sum"),
            n_equity_false=("equity_false_int", "sum"),
        )
        .reset_index()
    )

    for key in INSTRUMENT_KEYS:
        src = f"instrument_{key}_mentioned_int"
        dst = f"n_{key}_mentioned"
        counts = matched.groupby(group_cols, dropna=False)[src].sum().reset_index(name=dst)
        agg = agg.merge(counts, on=group_cols, how="left")

    static_df = matched[group_cols + static_cols].drop_duplicates(subset=group_cols)
    agg = agg.merge(static_df, on=group_cols, how="left")
    agg["equity_true_share_parse_ok"] = agg["n_equity_true"] / agg["n_parse_ok"].where(agg["n_parse_ok"] > 0)
    return agg.sort_values(["n_parse_ok", "n_target_postings"], ascending=[False, False])


def build_summary(postings: pd.DataFrame, firm_summary: pd.DataFrame, diagnostics: FirmMapDiagnostics) -> Dict[str, Any]:
    total = int(len(postings))
    with_output = int(postings["llm_has_output"].fillna(False).sum())
    parse_ok = int(postings["llm_parse_ok"].fillna(False).sum())
    matched = int(postings["firm_id"].notna().sum()) if "firm_id" in postings.columns else 0
    matched_parse_ok = int(postings.loc[postings["firm_id"].notna(), "llm_parse_ok"].fillna(False).sum())
    equity_true = int((postings["employee_equity_comp_offered"] == True).sum())
    equity_false = int((postings["employee_equity_comp_offered"] == False).sum())
    unmatched_companies = int(postings.loc[postings["firm_id"].isna(), "company_cleaned_norm"].nunique(dropna=True))
    match_source_counts: Dict[str, int] = {}
    if "firm_match_source" in postings.columns:
        vc = postings["firm_match_source"].fillna("none").value_counts(dropna=False)
        match_source_counts = {str(k): int(v) for k, v in vc.items()}

    return {
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "postings_total": total,
        "postings_with_output": with_output,
        "postings_parse_ok": parse_ok,
        "postings_firm_matched": matched,
        "postings_firm_matched_parse_ok": matched_parse_ok,
        "employee_equity_comp_offered_true": equity_true,
        "employee_equity_comp_offered_false": equity_false,
        "firms_with_any_matched_postings": int(firm_summary["firm_id"].nunique()) if not firm_summary.empty else 0,
        "unmatched_companies_count": unmatched_companies,
        "firm_match_source_counts": match_source_counts,
        "firm_map_diagnostics": {
            "n_rows_read": diagnostics.n_rows_read,
            "n_company_norm_unique": diagnostics.n_company_norm_unique,
            "n_company_with_multiple_firm_ids": diagnostics.n_company_with_multiple_firm_ids,
        },
    }


def main() -> None:
    args = parse_args()

    run_input_dir = args.run_input_dir.expanduser().resolve()
    run_output_dirs = [p.expanduser().resolve() for p in args.run_output_dir]
    firm_panel_csv = args.firm_panel_csv.expanduser().resolve()
    candidates_parquet = args.candidates_parquet.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()

    require_file(firm_panel_csv, nonempty=True, purpose="Firm panel CSV")
    ensure_dir(out_dir)

    inputs = load_input_requests(run_input_dir)
    outputs_frames: List[pd.DataFrame] = []
    for run_output_dir in run_output_dirs:
        if not run_output_dir.exists() or not run_output_dir.is_dir():
            raise RuntimeError(f"Run output dir does not exist or is not a directory: {run_output_dir}")
        outputs_frames.append(load_output_records(run_output_dir))
    outputs = pd.concat(outputs_frames, ignore_index=True) if outputs_frames else pd.DataFrame(columns=["custom_id"])
    if not outputs.empty:
        outputs = outputs.sort_values(["llm_parse_ok", "llm_has_output"], ascending=[False, False]).drop_duplicates(
            subset=["custom_id"], keep="first"
        )

    postings = inputs.merge(outputs, on="custom_id", how="left")
    if "llm_has_output" not in postings.columns:
        postings["llm_has_output"] = False
    if "llm_parse_ok" not in postings.columns:
        postings["llm_parse_ok"] = False
    postings["llm_has_output"] = postings["llm_has_output"].astype("boolean").fillna(False).astype(bool)
    postings["llm_parse_ok"] = postings["llm_parse_ok"].astype("boolean").fillna(False).astype(bool)

    job_ids = [j for j in postings["job_id"].dropna().astype(str).tolist() if j]
    candidate_metadata = load_candidate_metadata(candidates_parquet, job_ids)
    if not candidate_metadata.empty:
        postings = postings.merge(candidate_metadata, on="job_id", how="left")
        postings["company_cleaned"] = postings["company_cleaned"].combine_first(postings["candidate_company_cleaned"])
        postings["company_cleaned_norm"] = postings["company_cleaned"].map(normalize_company)
        postings["candidate_company_raw_norm"] = postings["candidate_company_raw"].map(normalize_company)
    if "candidate_gvkey_num" not in postings.columns:
        postings["candidate_gvkey_num"] = pd.NA
    if "candidate_company_raw_norm" not in postings.columns:
        postings["candidate_company_raw_norm"] = pd.NA

    company_map, gvkey_map, diagnostics = build_firm_maps(firm_panel_csv)
    company_map_prefixed = company_map.rename(columns={c: f"company_match_{c}" for c in company_map.columns})
    company_raw_map_prefixed = company_map.rename(columns={c: f"company_raw_match_{c}" for c in company_map.columns})
    gvkey_map_prefixed = gvkey_map.rename(columns={c: f"gvkey_match_{c}" for c in gvkey_map.columns})

    postings = postings.merge(
        gvkey_map_prefixed,
        left_on="candidate_gvkey_num",
        right_on="gvkey_match_gvkey_num",
        how="left",
    )
    postings = postings.merge(
        company_map_prefixed,
        left_on="company_cleaned_norm",
        right_on="company_match_company_norm",
        how="left",
    )
    postings = postings.merge(
        company_raw_map_prefixed,
        left_on="candidate_company_raw_norm",
        right_on="company_raw_match_company_norm",
        how="left",
    )

    field_names = ["firm_id", "companyname_panel", "org_uuid", "public", "startup", "remote", "teleworkable", "age", "industry", "hqstate", "gvkey"]
    for name in field_names:
        left = postings.get(f"gvkey_match_{name}")
        mid = postings.get(f"company_match_{name}")
        right = postings.get(f"company_raw_match_{name}")
        if left is None and mid is None and right is None:
            continue
        resolved = left if left is not None else pd.Series([pd.NA] * len(postings), index=postings.index)
        if mid is not None:
            resolved = resolved.combine_first(mid)
        if right is not None:
            resolved = resolved.combine_first(right)
        postings[name] = resolved

    postings["firm_match_source"] = pd.NA
    gvkey_match_firm = (
        postings["gvkey_match_firm_id"]
        if "gvkey_match_firm_id" in postings.columns
        else pd.Series([pd.NA] * len(postings), index=postings.index)
    )
    company_match_firm = (
        postings["company_match_firm_id"]
        if "company_match_firm_id" in postings.columns
        else pd.Series([pd.NA] * len(postings), index=postings.index)
    )
    company_raw_match_firm = (
        postings["company_raw_match_firm_id"]
        if "company_raw_match_firm_id" in postings.columns
        else pd.Series([pd.NA] * len(postings), index=postings.index)
    )
    postings.loc[gvkey_match_firm.notna(), "firm_match_source"] = "gvkey"
    postings.loc[postings["firm_match_source"].isna() & company_match_firm.notna(), "firm_match_source"] = "company_cleaned"
    postings.loc[postings["firm_match_source"].isna() & company_raw_match_firm.notna(), "firm_match_source"] = "company_raw"

    firm_summary = aggregate_firm_level(postings)
    unmatched = (
        postings.loc[postings["firm_id"].isna()]
        .groupby(["company_cleaned_norm"], dropna=True)
        .agg(
            n_target_postings=("custom_id", "size"),
            n_parse_ok=("llm_parse_ok", lambda s: int(s.fillna(False).sum())),
            n_equity_true=("employee_equity_comp_offered", lambda s: int((s == True).sum())),
            n_equity_false=("employee_equity_comp_offered", lambda s: int((s == False).sum())),
        )
        .reset_index()
        .sort_values("n_target_postings", ascending=False)
    )

    summary = build_summary(postings, firm_summary, diagnostics)

    run_label = args.run_label.strip() or run_input_dir.name
    postings_path = out_dir / f"{run_label}_postings_llm_firm_merge.csv"
    firms_path = out_dir / f"{run_label}_firm_equity_summary.csv"
    unmatched_path = out_dir / f"{run_label}_unmatched_companies.csv"
    summary_path = out_dir / f"{run_label}_merge_summary.json"

    postings.to_csv(postings_path, index=False)
    firm_summary.to_csv(firms_path, index=False)
    unmatched.to_csv(unmatched_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    latest_postings = out_dir / "latest_postings_llm_firm_merge.csv"
    latest_firms = out_dir / "latest_firm_equity_summary.csv"
    latest_unmatched = out_dir / "latest_unmatched_companies.csv"
    latest_summary = out_dir / "latest_merge_summary.json"

    postings.to_csv(latest_postings, index=False)
    firm_summary.to_csv(latest_firms, index=False)
    unmatched.to_csv(latest_unmatched, index=False)
    latest_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("Wrote posting-level merge:", postings_path)
    print("Wrote firm-level summary:", firms_path)
    print("Wrote unmatched diagnostics:", unmatched_path)
    print("Wrote merge summary:", summary_path)
    print("Summary stats:", summary)


if __name__ == "__main__":
    main()
