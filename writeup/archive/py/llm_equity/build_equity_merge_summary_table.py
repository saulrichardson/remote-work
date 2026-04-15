#!/usr/bin/env python3
"""Build a compact LaTeX summary table describing the merged equity-postings data.

This table is purely descriptive and economically oriented: it summarizes (i)
firm-level incidence of the main equity-offer indicator and (ii) basic post-period
posting counts describing the keyword + LLM pipeline.

Input:
  - results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv

Output:
  - results/cleaned/tex/llm_equity_merge_summary.tex
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import DATA_CLEAN, RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
INDENT: Final[str] = r"\hspace{1em}"

IN_PATH: Final[Path] = (
    RESULTS_RAW / "postings_description_equity" / "firm_merge" / "latest_firm_yh_llm_equity_enriched.csv"
)
OUT_PATH: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_merge_summary.tex"

# Matches the repo's "covid == 1" threshold (2020H1 starts 2020-01-01).
POST_START: Final[date] = date(2020, 1, 1)


def fmt_int(x: int) -> str:
    return f"{int(x):,}"


def fmt_pct(x: float, *, decimals: int = 2) -> str:
    return f"{x * 100:.{decimals}f}\\%"


def _as_date(series: pd.Series) -> pd.Series:
    # Expect ISO strings like '2020-01-01'. Coerce invalid to NaT.
    return pd.to_datetime(series, errors="coerce").dt.date


def _safe_bool(s: pd.Series) -> pd.Series:
    # Stata-like: treat missing as False.
    return s.fillna(0).astype(float).fillna(0).astype(int).astype(bool)


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [r"\centering", rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)
    in_path = require_file(IN_PATH, nonempty=True, purpose="enriched firm×half-year equity panel")

    # Restrict the descriptive summary to the analysis universe (the user panel used
    # in the productivity regressions), so counts align with the regression sample's
    # firm set.
    user_panel_path = require_file(
        DATA_CLEAN / "user_panel_precovid.dta",
        nonempty=True,
        purpose="user_panel_precovid.dta (analysis universe)",
    )
    user = pd.read_stata(
        user_panel_path,
        columns=["firm_id", "companyname", "yh", "startup"],
        convert_categoricals=False,
    )
    user["companyname"] = user["companyname"].astype(str)
    user["firm_id_key"] = user["companyname"].str.strip().str.lower()
    user.loc[user["firm_id_key"].isin({".", "", "nan", "none"}), "firm_id_key"] = pd.NA
    if user["firm_id_key"].isna().any():
        bad = int(user["firm_id_key"].isna().sum())
        raise RuntimeError(f"Found {bad} user-panel rows with missing/invalid companyname key; cannot merge equity panel.")

    # Unique firm×half-year cells in the analysis universe.
    cells = user[["firm_id", "firm_id_key", "yh", "startup"]].drop_duplicates().copy()
    if not pd.api.types.is_datetime64_any_dtype(cells["yh"]):
        raise RuntimeError("Expected user-panel yh to be a Stata date parsed as datetime64.")

    usecols = [
        "n_postings_desc_total",
        "n_keyword_hit_candidates",
        "n_llm_target_postings",
        "llm_n_parse_ok_raw",
        "llm_n_equity_true_raw",
        "llm_equity_any_raw",
        "firm_id_key",
        "yh",
    ]
    df = pd.read_csv(in_path, usecols=usecols)

    df = df.dropna(subset=["firm_id_key", "yh"]).copy()
    df["firm_id_key"] = df["firm_id_key"].astype(str).str.strip().str.lower()
    df["yh"] = pd.to_datetime(df["yh"], errors="coerce")
    if df["yh"].isna().any():
        bad = int(df["yh"].isna().sum())
        raise RuntimeError(f"Found {bad} rows with non-parseable yh in {in_path}. Expected ISO dates like YYYY-MM-DD.")
    df = df.drop_duplicates(subset=["firm_id_key", "yh"])

    # Merge onto the analysis-universe cells. Backfill convention: missing/unobserved
    # firm×half-year equity values are treated as 0.
    merged = cells.merge(df, on=["firm_id_key", "yh"], how="left", validate="m:1")
    merged["n_postings_desc_total"] = merged["n_postings_desc_total"].fillna(0).astype(int)
    merged["n_keyword_hit_candidates"] = merged["n_keyword_hit_candidates"].fillna(0).astype(int)
    merged["n_llm_target_postings"] = merged["n_llm_target_postings"].fillna(0).astype(int)
    merged["llm_n_parse_ok_raw"] = merged["llm_n_parse_ok_raw"].fillna(0).astype(int)
    merged["llm_n_equity_true_raw"] = merged["llm_n_equity_true_raw"].fillna(0).astype(int)
    merged["llm_equity_any_raw"] = merged["llm_equity_any_raw"].fillna(0).astype(int)

    merged["has_postings_cell"] = merged["n_postings_desc_total"] > 0
    merged["has_keyword_hit_cell"] = merged["n_keyword_hit_candidates"] > 0
    merged["llm_equity_pos_cell"] = merged["llm_equity_any_raw"] > 0
    merged["post"] = merged["yh"].dt.date >= POST_START

    # Firm-level measures used in the write-up:
    # - Offers equity: any LLM-classified equity-offer posting in any half-year
    firm = merged.groupby("firm_id", as_index=False).agg(
        startup=("startup", "max"),
        equity_exposure_post=("has_keyword_hit_cell", lambda s: bool((s & merged.loc[s.index, "post"]).any())),
        equity_offer_post=("llm_equity_pos_cell", lambda s: bool((s & merged.loc[s.index, "post"]).any())),
        equityfirm_ever=("llm_equity_pos_cell", "max"),
    )

    firm["equity_exposure_post"] = _safe_bool(firm["equity_exposure_post"])
    firm["equity_offer_post"] = _safe_bool(firm["equity_offer_post"])
    firm["equityfirm_ever"] = _safe_bool(firm["equityfirm_ever"])
    firm["startup"] = firm["startup"].fillna(0).astype(int)

    n_firms = int(firm.shape[0])
    n_startups = int((firm["startup"] == 1).sum())
    n_nonstartups = int((firm["startup"] == 0).sum())

    n_equityfirm = int(firm["equityfirm_ever"].sum())

    n_equityfirm_startup = int(((firm["startup"] == 1) & firm["equityfirm_ever"]).sum())
    n_equityfirm_nonstartup = int(((firm["startup"] == 0) & firm["equityfirm_ever"]).sum())

    def share(num: int, denom: int) -> float:
        return (num / denom) if denom else 0.0

    # Posting-level aggregates (counts + one simple headline share).
    # For Table 0 we aggregate across *all* half-years in the analysis universe,
    # since the point is to summarize the merged equity-postings data coverage.
    cells_all = merged.copy()
    cells_all["startup"] = cells_all["startup"].fillna(0).astype(int)

    def post_sums(mask: pd.Series) -> dict[str, float]:
        sub = cells_all.loc[mask]
        postings = float(sub["n_postings_desc_total"].sum())
        keyword = float(sub["n_keyword_hit_candidates"].sum())
        llm_equity = float(sub["llm_n_equity_true_raw"].sum())
        llm_target = float(sub["n_llm_target_postings"].sum())
        return {
            "postings": postings,
            "keyword": keyword,
            "llm_target": llm_target,
            "llm_equity": llm_equity,
            "offers_equity_rate": (llm_equity / postings) if postings > 0 else float("nan"),
        }

    sums_all = post_sums(mask=pd.Series(True, index=cells_all.index))
    sums_su = post_sums(mask=(cells_all["startup"] == 1))
    sums_ns = post_sums(mask=(cells_all["startup"] == 0))

    def fmt_rate(x: float) -> str:
        if pd.isna(x):
            return "--"
        return fmt_pct(float(x))

    lines: list[str] = [
        r" & All & Startups & Non-startups" + LB,
        MID,
        r"\multicolumn{4}{@{}l}{\textbf{\uline{Panel A: Firm-level incidence (analysis universe)}}}" + LB,
        r"\addlinespace[2pt]",
        rf"{INDENT}Firms (N) & {fmt_int(n_firms)} & {fmt_int(n_startups)} & {fmt_int(n_nonstartups)}" + LB,
        rf"{INDENT}Firms offering equity (N) & {fmt_int(n_equityfirm)} & {fmt_int(n_equityfirm_startup)} & {fmt_int(n_equityfirm_nonstartup)}"
        + LB,
        rf"{INDENT}Share of firms offering equity & {fmt_pct(share(n_equityfirm, n_firms))} & {fmt_pct(share(n_equityfirm_startup, n_startups))} & {fmt_pct(share(n_equityfirm_nonstartup, n_nonstartups))}"
        + LB,
        MID,
        r"\multicolumn{4}{@{}l}{\textbf{\uline{Panel B: Postings (counts; all half-years)}}}" + LB,
        r"\addlinespace[2pt]",
        rf"{INDENT}Postings with descriptions (sum) & {fmt_int(int(round(sums_all['postings'])))} & {fmt_int(int(round(sums_su['postings'])))} & {fmt_int(int(round(sums_ns['postings'])))}"
        + LB,
        rf"{INDENT}Equity-keyword-hit postings (sum) & {fmt_int(int(round(sums_all['keyword'])))} & {fmt_int(int(round(sums_su['keyword'])))} & {fmt_int(int(round(sums_ns['keyword'])))}"
        + LB,
        rf"{INDENT}LLM-processed postings (sum) & {fmt_int(int(round(sums_all['llm_target'])))} & {fmt_int(int(round(sums_su['llm_target'])))} & {fmt_int(int(round(sums_ns['llm_target'])))}"
        + LB,
        rf"{INDENT}Offers equity postings (LLM) (sum) & {fmt_int(int(round(sums_all['llm_equity'])))} & {fmt_int(int(round(sums_su['llm_equity'])))} & {fmt_int(int(round(sums_ns['llm_equity'])))}"
        + LB,
        rf"{INDENT}Share of postings offering equity (LLM) & {fmt_rate(sums_all['offers_equity_rate'])} & {fmt_rate(sums_su['offers_equity_rate'])} & {fmt_rate(sums_ns['offers_equity_rate'])}"
        + LB,
    ]

    tex = tabular_star(r"@{}l@{\extracolsep{\fill}}r@{\extracolsep{\fill}}r@{\extracolsep{\fill}}r@{}", lines)
    OUT_PATH.write_text(tex, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
