#!/usr/bin/env python3
"""Build LaTeX tables for the LLM-equity PI follow-up package."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file
from build_pi_followups_horse_race_firm import IN_RAW as HORSE_FIRM_RAW
from build_pi_followups_horse_race_firm import build_firm_horse_race_table
from build_pi_followups_horse_race_mini import IN_RAW as HORSE_MINI_RAW
from build_pi_followups_horse_race_mini import build_horse_race_table as build_mini_horse_race_table

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
PREAMBLE: Final[str] = r"\centering"
INDENT: Final[str] = r"\hspace{1em}"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

FIRM_RAW: Final[Path] = RESULTS_RAW / "firm_scaling_llm_equity_pi_followups" / "consolidated_results.csv"
USER_RAW: Final[Path] = RESULTS_RAW / "user_productivity_llm_equity_pi_followups_precovid" / "consolidated_results.csv"
PAIR_RAW: Final[Path] = RESULTS_RAW / "user_productivity_llm_equity_pair_fe_quick_precovid" / "consolidated_results.csv"
NO_CB_FIRM_RAW: Final[Path] = RESULTS_RAW / "firm_scaling_llm_equity_no_cb_modes" / "consolidated_results.csv"
NO_CB_USER_RAW: Final[Path] = RESULTS_RAW / "user_productivity_llm_equity_no_cb_modes_precovid" / "consolidated_results.csv"
NO_CB_SAMPLE_RAW: Final[Path] = RESULTS_RAW / "llm_equity_no_cb_modes" / "sample_accounting.csv"
NO_CB_SHARES_RAW: Final[Path] = RESULTS_RAW / "llm_equity_no_cb_modes" / "startup_vs_nonstartup_equity_shares.csv"
NO_CB_SHARES_RAW_LEGACY: Final[Path] = RESULTS_RAW / "llm_equity_no_cb_modes" / "startup_vs_large_equity_shares.csv"
NO_CB_INTENSIVE_RAW: Final[Path] = RESULTS_RAW / "llm_equity_no_cb_modes" / "intensive_margin_summary.csv"
AUDIT_RAW: Final[Path] = (
    RESULTS_RAW
    / "postings_description_equity"
    / "firm_merge"
    / "latest_llm_equity_backfill_audit_summary.csv"
)

STATUS_ROOT: Final[Path] = (
    RESULTS_RAW
    / "postings_description_equity"
    / "llm_batch_inputs"
    / "equity_candidates"
)

OUT_STATUS: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_status_cli.tex"
OUT_AUDIT: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_coverage_audit.tex"
OUT_FIRM_GRID: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_grid.tex"
OUT_FIRM_MEASURE_SOFTWARE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_software.tex"
OUT_FIRM_MEASURE_COUNT: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_count.tex"
OUT_FIRM_MEASURE_TOPQ: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_firm_measure_topq.tex"
OUT_USER_GRID: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_grid.tex"
OUT_USER_MEASURE_SOFTWARE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_software.tex"
OUT_USER_MEASURE_COUNT: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_count.tex"
OUT_USER_MEASURE_TOPQ: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_user_measure_topq.tex"
OUT_PAIR: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_pair_fe_quick.tex"
OUT_HORSE_FIRM: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_horse_race_firm.tex"
OUT_HORSE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_horse_race.tex"
OUT_ANCHOR_SAMPLE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_sample.tex"
OUT_ANCHOR_DESC: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_descriptives.tex"
OUT_ANCHOR_FIRM: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_firm_core.tex"
OUT_ANCHOR_USER: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_anchor_user_core.tex"
OUT_REDUCED1_FIRM: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_reduced1_firm.tex"
OUT_REDUCED1_USER: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_pi_followups_reduced1_user.tex"

MEASURE_ORDER: Final[list[str]] = [
    "any_software_strict",
    "count_raw",
    "share_top_quartile",
]

MEASURE_LABEL: Final[dict[str, str]] = {
    "any_software_strict": "Any equity mention (software roles only)",
    "count_raw": "Average number of equity mentions",
    "share_top_quartile": "High equity-share indicator (top quartile)",
}

SAMPLE_COLS: Final[list[tuple[str, str, str, str]]] = [
    ("backfill", "core_pooled", "OLS", "Main OLS"),
    ("backfill", "core_pooled", "IV", "Main IV"),
]

FULL_SPEC_COLS: Final[list[tuple[str, str, str]]] = [
    ("backfill", "core_pooled", "Main spec"),
    ("backfill_missing", "core_pooled_missing_ctrl", "+No-parse-share control"),
    ("backfill_decomp", "core_pooled_decomp_ctrl", "+No-keyword/unparsed controls"),
]


def stars(p: float) -> str:
    for cutoff, symbol in STAR_RULES:
        if p < cutoff:
            return symbol
    return ""


def fmt_coef(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1e4 or (0 < abs_v < 1e-2):
        return f"{value:.2e}"
    return f"{value:.2f}"


def fmt_int(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{int(round(float(value))):,}"


def latex_escape(text: str) -> str:
    out = text.replace("\\", r"\textbackslash{}")
    out = out.replace("&", r"\&")
    out = out.replace("%", r"\%")
    out = out.replace("_", r"\_")
    return out


def coef_cell(row: pd.Series | None) -> str:
    if row is None:
        return "--"
    coef = row.get("coef")
    se = row.get("se")
    pval = row.get("pval")
    if coef is None or se is None or pd.isna(coef) or pd.isna(se):
        return "--"
    if float(se) == 0.0:
        return "--"
    p = float(pval) if pval is not None and not pd.isna(pval) else 1.0
    return rf"\makecell[c]{{{fmt_coef(float(coef))}{stars(p)}\\({fmt_coef(float(se))})}}"


def stat_cell(row: pd.Series | None, field: str, fmt: str = "{:,.0f}") -> str:
    if row is None:
        return "--"
    value = row.get(field)
    if value is None or pd.isna(value):
        return "--"
    return fmt.format(value)


def tabular(colspec: str, body_lines: list[str]) -> str:
    lines = [PREAMBLE, rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def tabular_resized(colspec: str, body_lines: list[str], *, tabcolsep_pt: int = 3) -> str:
    lines = [
        PREAMBLE,
        "{",
        rf"\setlength{{\tabcolsep}}{{{tabcolsep_pt}pt}}",
        r"\resizebox{\linewidth}{!}{%",
        rf"\begin{{tabular}}{{{colspec}}}",
        TOP,
    ]
    lines.extend(body_lines)
    lines.extend(
        [
            BOTTOM,
            r"\end{tabular}%",
            "}",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


def find_status_summary() -> tuple[Path, dict]:
    candidates = sorted(STATUS_ROOT.rglob("status_dir_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No status_dir_summary.json found under {STATUS_ROOT}")
    path = candidates[0]
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return path, payload


def build_status_table(status_path: Path, payload: dict) -> str:
    status_counts = payload.get("status_counts", {})
    req = payload.get("request_totals", {})
    completed = int(req.get("completed", 0))
    failed = int(req.get("failed", 0))
    total = int(req.get("total", 0))
    completion_rate = (completed / total) if total > 0 else 0.0
    failed_rate = (failed / total) if total > 0 else 0.0

    batch_total = sum(int(v) for v in status_counts.values()) if status_counts else 0
    batch_completed = int(status_counts.get("completed", 0))

    rows = [
        r"Metric & Value" + LB,
        MID,
        rf"Status snapshot file & \texttt{{{latex_escape(status_path.name)}}}" + LB,
        "Batch jobs (total) & " + fmt_int(batch_total) + LB,
        "Batch jobs completed & " + fmt_int(batch_completed) + LB,
        "Requests (completed) & " + fmt_int(completed) + LB,
        "Requests (failed) & " + fmt_int(failed) + LB,
        "Requests (total) & " + fmt_int(total) + LB,
        "Completion rate & " + latex_escape(f"{completion_rate:.2%}") + LB,
        "Failure rate & " + latex_escape(f"{failed_rate:.3%}") + LB,
    ]
    return tabular(r"@{}l@{\extracolsep{\fill}}r@{}", rows)


def pretty_audit_status(name: str) -> str:
    mapping = {
        "backfill_no_postings": "No postings in cell",
        "backfill_no_keyword_hit": "Postings observed, no equity keyword hit",
        "backfill_keyword_unparsed": "Keyword hit, not parse-routed",
        "observed_positive": "Observed: equity-positive",
        "observed_true_zero": "Observed: parseable true zero",
    }
    return mapping.get(name, name.replace("_", " "))


def build_audit_table(df: pd.DataFrame) -> str:
    cols = {"status_name", "n_firm_yh_rows", "n_firms", "share_firm_yh_rows"}
    missing = cols - set(df.columns)
    if missing:
        raise RuntimeError(f"Audit summary missing expected columns: {sorted(missing)}")

    work = df.copy()
    work = work.sort_values("n_firm_yh_rows", ascending=False)
    rows = [
        "Classification status & Firm$\\times$half-year rows & Share of rows & Firms" + LB,
        MID,
    ]
    for _, r in work.iterrows():
        share_text = latex_escape(f"{float(r['share_firm_yh_rows']):.2%}")
        rows.append(
            f"{pretty_audit_status(str(r['status_name']))} & "
            f"{fmt_int(r['n_firm_yh_rows'])} & "
            f"{share_text} & "
            f"{fmt_int(r['n_firms'])}"
            + LB
        )
    return tabular(r"@{}l@{\extracolsep{\fill}}r@{\extracolsep{\fill}}r@{\extracolsep{\fill}}r@{}", rows)


def build_anchor_sample_backfill_table(sample_df: pd.DataFrame) -> str:
    needed = {
        "sample_mode",
        "n_rows",
        "n_firms",
        "n_rows_parse_ok",
        "n_startup_firms",
        "n_firms_equity_any",
    }
    missing = needed - set(sample_df.columns)
    if missing:
        raise RuntimeError(f"No-CB sample accounting is missing columns: {sorted(missing)}")

    row = sample_df[sample_df["sample_mode"] == "backfill"].head(1)
    if row.empty:
        raise RuntimeError("No backfill row found in no-CB sample accounting")
    r = row.iloc[0]
    nonstartup_col = "n_nonstartup_firms" if "n_nonstartup_firms" in sample_df.columns else "n_large_firms"
    if nonstartup_col not in sample_df.columns:
        raise RuntimeError("No non-startup firm count column found in no-CB sample accounting")

    rows = [
        "Metric & Value" + LB,
        MID,
        "Firm$\\times$half-year rows & " + fmt_int(r["n_rows"]) + LB,
        "Firms & " + fmt_int(r["n_firms"]) + LB,
        "Startup firms & " + fmt_int(r["n_startup_firms"]) + LB,
        "Non-startup firms & " + fmt_int(r[nonstartup_col]) + LB,
        "Firms with any equity signal & " + fmt_int(r["n_firms_equity_any"]) + LB,
    ]
    return tabular(r"@{}l@{\extracolsep{\fill}}r@{}", rows)


def build_anchor_descriptives_backfill_table(shares_df: pd.DataFrame, intensive_df: pd.DataFrame) -> str:
    merged = shares_df.merge(intensive_df, on=["sample_mode", "firm_group", "n_firms"], how="left")
    work = merged[merged["sample_mode"] == "backfill"].copy()
    if work.empty:
        raise RuntimeError("No backfill rows found for startup/non-startup descriptives")

    group_order = {"startup": 0, "non_startup": 1, "large": 1}
    group_label = {"startup": "Startup", "non_startup": "Non-startup", "large": "Non-startup"}
    work["group_order"] = work["firm_group"].map(group_order).fillna(99)
    work = work.sort_values("group_order")

    rows = [
        r"Firm group & Firms & \% any equity & Mean share & Median share & Mean count & Median count" + LB,
        MID,
    ]
    for _, r in work.iterrows():
        rows.append(
            " & ".join(
                [
                    group_label.get(str(r["firm_group"]), str(r["firm_group"])),
                    fmt_int(r["n_firms"]),
                    "--" if pd.isna(r.get("pct_equity_any")) else f"{100.0 * float(r['pct_equity_any']):.1f}",
                    "--" if pd.isna(r.get("mean_eq_share_firm")) else f"{float(r['mean_eq_share_firm']):.3f}",
                    "--" if pd.isna(r.get("median_eq_share_firm")) else f"{float(r['median_eq_share_firm']):.3f}",
                    "--" if pd.isna(r.get("mean_eq_count_firm")) else f"{float(r['mean_eq_count_firm']):.3f}",
                    "--" if pd.isna(r.get("median_eq_count_firm")) else f"{float(r['median_eq_count_firm']):.3f}",
                ]
            )
            + LB
        )
    return tabular(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", rows)


def find_no_cb_backfill_core_row(df: pd.DataFrame, *, model_type: str, outcome: str, param: str) -> pd.Series | None:
    subset = df[
        (df["sample_mode"] == "backfill")
        & (df["analysis_block"] == "core_pooled")
        & (df["equity_measure"] == "any")
        & (df["split_group"] == "all")
        & (df["model_type"] == model_type)
        & (df["outcome"] == outcome)
        & (df["param"] == param)
    ].head(1)
    if subset.empty:
        return None
    return subset.iloc[0]


def find_no_cb_row(
    df: pd.DataFrame,
    *,
    sample_mode: str,
    analysis_block: str,
    equity_measure: str,
    split_group: str,
    model_type: str,
    outcome: str,
    param: str,
) -> pd.Series | None:
    subset = df[
        (df["sample_mode"] == sample_mode)
        & (df["analysis_block"] == analysis_block)
        & (df["equity_measure"] == equity_measure)
        & (df["split_group"] == split_group)
        & (df["model_type"] == model_type)
        & (df["outcome"] == outcome)
        & (df["param"] == param)
    ].head(1)
    if subset.empty:
        return None
    return subset.iloc[0]


def build_reduced1_backfill_table(df: pd.DataFrame, *, outcome: str, include_users: bool) -> str:
    params = [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var3_eq_any", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Offers equity} $"),
        ("eq_any_firm_covid", r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) $"),
    ]
    lines = [
        "Parameter & OLS & IV" + LB,
        " & (1) & (2)" + LB,
        MID,
    ]
    for param, label in params:
        row_ols = find_no_cb_row(
            df,
            sample_mode="backfill",
            analysis_block="reduced1",
            equity_measure="any",
            split_group="all",
            model_type="OLS",
            outcome=outcome,
            param=param,
        )
        row_iv = find_no_cb_row(
            df,
            sample_mode="backfill",
            analysis_block="reduced1",
            equity_measure="any",
            split_group="all",
            model_type="IV",
            outcome=outcome,
            param=param,
        )
        lines.append(INDENT + label + " & " + coef_cell(row_ols) + " & " + coef_cell(row_iv) + LB)

    ref_ols = find_no_cb_row(
        df,
        sample_mode="backfill",
        analysis_block="reduced1",
        equity_measure="any",
        split_group="all",
        model_type="OLS",
        outcome=outcome,
        param="var3",
    )
    ref_iv = find_no_cb_row(
        df,
        sample_mode="backfill",
        analysis_block="reduced1",
        equity_measure="any",
        split_group="all",
        model_type="IV",
        outcome=outcome,
        param="var3",
    )
    lines.extend(
        [
            MID,
            "Pre-shift mean & " + stat_cell(ref_ols, "pre_mean", "{:.2f}") + " & " + stat_cell(ref_iv, "pre_mean", "{:.2f}") + LB,
            "KP rk Wald F &  & " + stat_cell(ref_iv, "rkf", "{:.2f}") + LB,
            "N & " + stat_cell(ref_ols, "nobs") + " & " + stat_cell(ref_iv, "nobs") + LB,
            "Firms & " + stat_cell(ref_ols, "n_firms") + " & " + stat_cell(ref_iv, "n_firms") + LB,
        ]
    )
    if include_users:
        lines.append("Users & " + stat_cell(ref_ols, "n_users") + " & " + stat_cell(ref_iv, "n_users") + LB)

    lines.extend(
        [
            MID,
            r"\textbf{Controls Included} &  & " + LB,
            INDENT + r"Firm & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Half-year & $\checkmark$ & $\checkmark$" + LB,
        ]
    )
    if include_users:
        lines.append(INDENT + r"Individual & $\checkmark$ & $\checkmark$" + LB)

    return tabular(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", lines)


def build_anchor_core_backfill_table(df: pd.DataFrame, *, outcome: str, include_users: bool) -> str:
    params = [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
        ("var3_eq_any", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Offers equity} $"),
        ("var5_eq_any", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{Offers equity} $"),
        ("eq_any_firm_covid", r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) $"),
    ]
    lines = [
        "Parameter & OLS & IV" + LB,
        " & (1) & (2)" + LB,
        MID,
    ]
    for param, label in params:
        row_ols = find_no_cb_backfill_core_row(df, model_type="OLS", outcome=outcome, param=param)
        row_iv = find_no_cb_backfill_core_row(df, model_type="IV", outcome=outcome, param=param)
        lines.append(INDENT + label + " & " + coef_cell(row_ols) + " & " + coef_cell(row_iv) + LB)

    ref_ols = find_no_cb_backfill_core_row(df, model_type="OLS", outcome=outcome, param="var5")
    ref_iv = find_no_cb_backfill_core_row(df, model_type="IV", outcome=outcome, param="var5")
    lines.extend(
        [
            MID,
            "Pre-shift mean & " + stat_cell(ref_ols, "pre_mean", "{:.2f}") + " & " + stat_cell(ref_iv, "pre_mean", "{:.2f}") + LB,
            "KP rk Wald F &  & " + stat_cell(ref_iv, "rkf", "{:.2f}") + LB,
            "N & " + stat_cell(ref_ols, "nobs") + " & " + stat_cell(ref_iv, "nobs") + LB,
            "Firms & " + stat_cell(ref_ols, "n_firms") + " & " + stat_cell(ref_iv, "n_firms") + LB,
        ]
    )
    if include_users:
        lines.append("Users & " + stat_cell(ref_ols, "n_users") + " & " + stat_cell(ref_iv, "n_users") + LB)

    lines.extend(
        [
            MID,
            r"\textbf{Controls Included} &  & " + LB,
            INDENT + "Firm & " + r"$\checkmark$ & $\checkmark$" + LB,
            INDENT + "Half-year & " + r"$\checkmark$ & $\checkmark$" + LB,
        ]
    )
    if include_users:
        lines.append(INDENT + "Individual & " + r"$\checkmark$ & $\checkmark$" + LB)

    return tabular(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", lines)


def find_measure_row(
    df: pd.DataFrame,
    *,
    sample_mode: str,
    analysis_block: str,
    model_type: str,
    equity_measure: str,
    param: str = "var5",
) -> pd.Series | None:
    subset = df[
        (df["sample_mode"] == sample_mode)
        & (df["analysis_block"] == analysis_block)
        & (df["model_type"] == model_type)
        & (df["equity_measure"] == equity_measure)
        & (df["param"] == param)
    ].head(1)
    if subset.empty:
        return None
    return subset.iloc[0]


def build_measure_grid_table(df: pd.DataFrame, *, include_users: bool) -> str:
    lines = [
        "Equity definition & OLS & IV" + LB,
        " & (1) & (2)" + LB,
        MID,
    ]

    for measure in MEASURE_ORDER:
        label = MEASURE_LABEL.get(measure, measure)
        lines.append(INDENT + r"\textit{" + label + "}" + " &  & " + LB)

        row_cache: dict[tuple[str, str], pd.Series | None] = {}
        for param, param_label in [
            ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
            ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
        ]:
            cells: list[str] = []
            for sample_mode, block, model_type, _ in SAMPLE_COLS:
                row = find_measure_row(
                    df,
                    sample_mode=sample_mode,
                    analysis_block=block,
                    model_type=model_type,
                    equity_measure=measure,
                    param=param,
                )
                row_cache[(model_type, param)] = row
                cells.append(coef_cell(row))
            lines.append(INDENT + INDENT + param_label + " & " + " & ".join(cells) + LB)
        lines.append(INDENT + INDENT + r"\textit{N}" + " & " + " & ".join(
            [
                stat_cell(row_cache.get(("OLS", "var5")), "nobs"),
                stat_cell(row_cache.get(("IV", "var5")), "nobs"),
            ]
        ) + LB)
        lines.append(INDENT + INDENT + r"\textit{Firms}" + " & " + " & ".join(
            [
                stat_cell(row_cache.get(("OLS", "var5")), "n_firms"),
                stat_cell(row_cache.get(("IV", "var5")), "n_firms"),
            ]
        ) + LB)
        if include_users:
            lines.append(INDENT + INDENT + r"\textit{Users}" + " & " + " & ".join(
                [
                    stat_cell(row_cache.get(("OLS", "var5")), "n_users"),
                    stat_cell(row_cache.get(("IV", "var5")), "n_users"),
                ]
            ) + LB)
        lines.append(INDENT + INDENT + r"\textit{KP rk Wald F}" + " & " + " & ".join(
            [
                "",
                stat_cell(row_cache.get(("IV", "var5")), "rkf", "{:.2f}"),
            ]
        ) + LB)
        lines.append(MID)

    colspec = r"@{}p{0.42\linewidth}" + (r"c" * 2) + r"@{}"
    return tabular_resized(colspec, lines, tabcolsep_pt=2)


def build_single_measure_table(df: pd.DataFrame, *, include_users: bool, measure: str) -> str:
    lines = [
        "Parameter & OLS & IV" + LB,
        " & (1) & (2)" + LB,
        MID,
    ]

    row_cache: dict[tuple[str, str], pd.Series | None] = {}
    for param, param_label in [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
    ]:
        cells: list[str] = []
        for sample_mode, block, model_type, _ in SAMPLE_COLS:
            row = find_measure_row(
                df,
                sample_mode=sample_mode,
                analysis_block=block,
                model_type=model_type,
                equity_measure=measure,
                param=param,
            )
            row_cache[(model_type, param)] = row
            cells.append(coef_cell(row))
        lines.append(INDENT + param_label + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & "
            + " & ".join(
                [
                    stat_cell(row_cache.get(("OLS", "var5")), "nobs"),
                    stat_cell(row_cache.get(("IV", "var5")), "nobs"),
                ]
            )
            + LB,
            "Firms & "
            + " & ".join(
                [
                    stat_cell(row_cache.get(("OLS", "var5")), "n_firms"),
                    stat_cell(row_cache.get(("IV", "var5")), "n_firms"),
                ]
            )
            + LB,
        ]
    )
    if include_users:
        lines.append(
            "Users & "
            + " & ".join(
                [
                    stat_cell(row_cache.get(("OLS", "var5")), "n_users"),
                    stat_cell(row_cache.get(("IV", "var5")), "n_users"),
                ]
            )
            + LB
        )

    lines.append(
        "KP rk Wald F & "
        + " & ".join(
            [
                "",
                stat_cell(row_cache.get(("IV", "var5")), "rkf", "{:.2f}"),
            ]
        )
        + LB
    )
    return tabular(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", lines)


def build_full_spec_measure_table(df: pd.DataFrame, *, include_users: bool, measure: str) -> str:
    header_labels = [spec_label for _, _, spec_label in FULL_SPEC_COLS]
    lines = [
        rf" & \multicolumn{{2}}{{c}}{{{header_labels[0]}}} & \multicolumn{{2}}{{c}}{{{header_labels[1]}}} & \multicolumn{{2}}{{c}}{{{header_labels[2]}}}" + LB,
        r"\cmidrule(lr){2-3}",
        r"\cmidrule(lr){4-5}",
        r"\cmidrule(lr){6-7}",
        "Coefficient & OLS & IV & OLS & IV & OLS & IV" + LB,
        " & (1) & (2) & (3) & (4) & (5) & (6)" + LB,
        MID,
    ]

    def pull(sample_mode: str, analysis_block: str, model_type: str, param: str) -> pd.Series | None:
        return find_measure_row(
            df,
            sample_mode=sample_mode,
            analysis_block=analysis_block,
            model_type=model_type,
            equity_measure=measure,
            param=param,
        )

    def coef_row(param: str, label: str) -> str:
        cells: list[str] = []
        for sample_mode, analysis_block, _ in FULL_SPEC_COLS:
            cells.append(coef_cell(pull(sample_mode, analysis_block, "OLS", param)))
            cells.append(coef_cell(pull(sample_mode, analysis_block, "IV", param)))
        return INDENT + label + " & " + " & ".join(cells) + LB

    core_params = [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
        ("var3_eq", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Equity} $"),
        ("var5_eq", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{Equity} $"),
    ]
    extra_params = [
        ("miss_parse_share_firm_covid", r"$ \text{NoParseShare} \times \mathds{1}(\text{Post}) $"),
        ("no_keyword_share_firm_covid", r"$ \text{NoKeywordShare} \times \mathds{1}(\text{Post}) $"),
        ("unparsed_hit_share_firm_covid", r"$ \text{UnparsedHitShare} \times \mathds{1}(\text{Post}) $"),
    ]

    for param, label in core_params:
        lines.append(coef_row(param, label))
    lines.append(MID)
    for param, label in extra_params:
        lines.append(coef_row(param, label))

    def stat_values(field: str, fmt: str = "{:,.0f}") -> str:
        vals: list[str] = []
        for sample_mode, analysis_block, _ in FULL_SPEC_COLS:
            vals.append(stat_cell(pull(sample_mode, analysis_block, "OLS", "var5"), field, fmt))
            vals.append(stat_cell(pull(sample_mode, analysis_block, "IV", "var5"), field, fmt))
        return " & ".join(vals)

    kp_vals: list[str] = []
    for sample_mode, analysis_block, _ in FULL_SPEC_COLS:
        kp_vals.append("")
        kp_vals.append(stat_cell(pull(sample_mode, analysis_block, "IV", "var5"), "rkf", "{:.2f}"))

    lines.extend(
        [
            MID,
            "N & " + stat_values("nobs") + LB,
            "Firms & " + stat_values("n_firms") + LB,
        ]
    )
    if include_users:
        lines.append("Users & " + stat_values("n_users") + LB)
    lines.append("KP rk Wald F & " + " & ".join(kp_vals) + LB)

    checks_all = " & ".join([r"$\checkmark$"] * 6)
    missing_checks = " & ".join(["", "", r"$\checkmark$", r"$\checkmark$", "", ""])
    decomp_checks = " & ".join(["", "", "", "", r"$\checkmark$", r"$\checkmark$"])
    lines.extend(
        [
            MID,
            r"\textbf{Controls Included} &  &  &  &  &  & " + LB,
            INDENT + "Firm & " + checks_all + LB,
            INDENT + "Half-year & " + checks_all + LB,
        ]
    )
    if include_users:
        lines.append(INDENT + "Individual & " + checks_all + LB)
    lines.append(INDENT + "No-parse-share control & " + missing_checks + LB)
    lines.append(INDENT + "No-keyword/unparsed controls & " + decomp_checks + LB)

    colspec = r"@{}p{0.43\linewidth}" + (r"c" * 6) + r"@{}"
    return tabular_resized(colspec, lines, tabcolsep_pt=2)


def find_pair_row(df: pd.DataFrame, *, fe_variant: str, model_type: str, param: str) -> pd.Series | None:
    subset = df[
        (df["fe_variant"] == fe_variant)
        & (df["model_type"] == model_type)
        & (df["param"] == param)
    ].head(1)
    if subset.empty:
        return None
    return subset.iloc[0]


def build_pair_table(df: pd.DataFrame) -> str:
    cols = [
        ("baseline_fe", "OLS"),
        ("baseline_fe", "IV"),
        ("pair_fe", "OLS"),
        ("pair_fe", "IV"),
    ]
    lines = [
        r" & \multicolumn{2}{c}{Baseline FE} & \multicolumn{2}{c}{Person$\times$Firm FE}" + LB,
        r"\cmidrule(lr){2-3}",
        r"\cmidrule(lr){4-5}",
        "Parameter & OLS & IV & OLS & IV" + LB,
        " & (1) & (2) & (3) & (4)" + LB,
        MID,
    ]

    for param, label in [
        ("var3", "Main remote effect"),
        ("var5", "Main startup effect"),
    ]:
        cells = []
        for fe_variant, model_type in cols:
            cells.append(coef_cell(find_pair_row(df, fe_variant=fe_variant, model_type=model_type, param=param)))
        lines.append(INDENT + label + " & " + " & ".join(cells) + LB)

    lines.append(MID)
    for field, label in [("nobs", "N"), ("n_firms", "Firms"), ("n_users", "Users")]:
        vals = []
        for fe_variant, model_type in cols:
            ref = find_pair_row(df, fe_variant=fe_variant, model_type=model_type, param="var5")
            vals.append(stat_cell(ref, field))
        lines.append(label + " & " + " & ".join(vals) + LB)

    rk_vals = []
    for fe_variant, model_type in cols:
        ref = find_pair_row(df, fe_variant=fe_variant, model_type=model_type, param="var5")
        if model_type == "IV":
            rk_vals.append(stat_cell(ref, "rkf", "{:.2f}"))
        else:
            rk_vals.append("")
    lines.append("KP rk Wald F & " + " & ".join(rk_vals) + LB)

    checks = " & ".join([r"$\checkmark$"] * 4)
    lines.extend(
        [
            MID,
            r"\textbf{Controls Included} &  &  &  & " + LB,
            INDENT + "Firm & " + checks + LB,
            INDENT + "Half-year & " + checks + LB,
            INDENT + "Individual & " + checks + LB,
            INDENT + r"Person$\times$Firm &  &  & $\checkmark$ & $\checkmark$" + LB,
        ]
    )

    return tabular(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", lines)


def find_horse_row(df: pd.DataFrame, *, spec: str, model_type: str, param: str = "var5") -> pd.Series | None:
    subset = df[(df["spec"] == spec) & (df["model_type"] == model_type) & (df["param"] == param)].head(1)
    if subset.empty:
        return None
    return subset.iloc[0]


def build_horse_table(df: pd.DataFrame) -> str:
    specs = ["baseline", "labor_scaling", "equity_comp", "labor_scaling_equity_comp"]
    spec_labels = ["Baseline", "+Labor scaling", "+Equity comp", "+Both"]

    lines = [
        "Specification & " + " & ".join(spec_labels) + LB,
        " & (1) & (2) & (3) & (4)" + LB,
        MID,
    ]

    ols_cells = [coef_cell(find_horse_row(df, spec=s, model_type="OLS")) for s in specs]
    iv_cells = [coef_cell(find_horse_row(df, spec=s, model_type="IV")) for s in specs]
    lines.append(
        INDENT + "Main startup effect (OLS) & " + " & ".join(ols_cells) + LB
    )
    lines.append(
        INDENT + "Main startup effect (IV) & " + " & ".join(iv_cells) + LB
    )
    lines.append(MID)

    labor_checks = [r"$\checkmark$" if s in {"labor_scaling", "labor_scaling_equity_comp"} else "" for s in specs]
    equity_checks = [r"$\checkmark$" if s in {"equity_comp", "labor_scaling_equity_comp"} else "" for s in specs]
    lines.append("Labor-scaling controls & " + " & ".join(labor_checks) + LB)
    lines.append("Equity-comp controls & " + " & ".join(equity_checks) + LB)

    lines.append(MID)
    n_ols = [stat_cell(find_horse_row(df, spec=s, model_type="OLS"), "nobs") for s in specs]
    n_iv = [stat_cell(find_horse_row(df, spec=s, model_type="IV"), "nobs") for s in specs]
    kp = [stat_cell(find_horse_row(df, spec=s, model_type="IV"), "rkf", "{:.2f}") for s in specs]
    lines.append("N (OLS) & " + " & ".join(n_ols) + LB)
    lines.append("N (IV) & " + " & ".join(n_iv) + LB)
    lines.append("KP rk Wald F & " + " & ".join(kp) + LB)

    checks = " & ".join([r"$\checkmark$"] * 4)
    lines.extend(
        [
            MID,
            r"\textbf{Controls Included} &  &  &  & " + LB,
            INDENT + "Firm & " + checks + LB,
            INDENT + "Half-year & " + checks + LB,
            INDENT + "Individual & " + checks + LB,
        ]
    )

    return tabular(r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}", lines)


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)

    firm_df = pd.read_csv(require_file(FIRM_RAW, nonempty=True, purpose="firm PI follow-up results"))
    user_df = pd.read_csv(require_file(USER_RAW, nonempty=True, purpose="user PI follow-up results"))
    pair_df = pd.read_csv(require_file(PAIR_RAW, nonempty=True, purpose="pair FE quick-check results"))
    horse_firm_df = pd.read_csv(require_file(HORSE_FIRM_RAW, nonempty=True, purpose="firm horse-race results"))
    horse_df = pd.read_csv(
        require_file(HORSE_MINI_RAW, nonempty=True, purpose="mini-style mechanisms horse-race results")
    )
    audit_df = pd.read_csv(require_file(AUDIT_RAW, nonempty=True, purpose="backfill audit summary"))
    no_cb_firm_df = pd.read_csv(require_file(NO_CB_FIRM_RAW, nonempty=True, purpose="no-CB firm results"))
    no_cb_user_df = pd.read_csv(require_file(NO_CB_USER_RAW, nonempty=True, purpose="no-CB user results"))
    no_cb_sample_df = pd.read_csv(require_file(NO_CB_SAMPLE_RAW, nonempty=True, purpose="no-CB sample accounting"))
    no_cb_intensive_df = pd.read_csv(require_file(NO_CB_INTENSIVE_RAW, nonempty=True, purpose="no-CB intensive summary"))
    no_cb_shares_path = NO_CB_SHARES_RAW if NO_CB_SHARES_RAW.exists() else NO_CB_SHARES_RAW_LEGACY
    no_cb_shares_df = pd.read_csv(require_file(no_cb_shares_path, nonempty=True, purpose="no-CB startup/non-startup shares"))
    status_path, status_payload = find_status_summary()

    OUT_STATUS.write_text(build_status_table(status_path, status_payload), encoding="utf-8")
    OUT_AUDIT.write_text(build_audit_table(audit_df), encoding="utf-8")
    OUT_ANCHOR_SAMPLE.write_text(build_anchor_sample_backfill_table(no_cb_sample_df), encoding="utf-8")
    OUT_ANCHOR_DESC.write_text(
        build_anchor_descriptives_backfill_table(no_cb_shares_df, no_cb_intensive_df),
        encoding="utf-8",
    )
    OUT_ANCHOR_FIRM.write_text(
        build_anchor_core_backfill_table(no_cb_firm_df, outcome="growth_rate_we", include_users=False),
        encoding="utf-8",
    )
    OUT_ANCHOR_USER.write_text(
        build_anchor_core_backfill_table(no_cb_user_df, outcome="total_contributions_q100", include_users=True),
        encoding="utf-8",
    )
    OUT_REDUCED1_FIRM.write_text(
        build_reduced1_backfill_table(no_cb_firm_df, outcome="growth_rate_we", include_users=False),
        encoding="utf-8",
    )
    OUT_REDUCED1_USER.write_text(
        build_reduced1_backfill_table(no_cb_user_df, outcome="total_contributions_q100", include_users=True),
        encoding="utf-8",
    )
    OUT_FIRM_GRID.write_text(build_measure_grid_table(firm_df, include_users=False), encoding="utf-8")
    OUT_USER_GRID.write_text(build_measure_grid_table(user_df, include_users=True), encoding="utf-8")
    OUT_FIRM_MEASURE_SOFTWARE.write_text(
        build_full_spec_measure_table(firm_df, include_users=False, measure="any_software_strict"),
        encoding="utf-8",
    )
    OUT_FIRM_MEASURE_COUNT.write_text(
        build_full_spec_measure_table(firm_df, include_users=False, measure="count_raw"),
        encoding="utf-8",
    )
    OUT_FIRM_MEASURE_TOPQ.write_text(
        build_full_spec_measure_table(firm_df, include_users=False, measure="share_top_quartile"),
        encoding="utf-8",
    )
    OUT_USER_MEASURE_SOFTWARE.write_text(
        build_full_spec_measure_table(user_df, include_users=True, measure="any_software_strict"),
        encoding="utf-8",
    )
    OUT_USER_MEASURE_COUNT.write_text(
        build_full_spec_measure_table(user_df, include_users=True, measure="count_raw"),
        encoding="utf-8",
    )
    OUT_USER_MEASURE_TOPQ.write_text(
        build_full_spec_measure_table(user_df, include_users=True, measure="share_top_quartile"),
        encoding="utf-8",
    )
    OUT_PAIR.write_text(build_pair_table(pair_df), encoding="utf-8")
    OUT_HORSE_FIRM.write_text(build_firm_horse_race_table(horse_firm_df, outcome="growth_rate_we"), encoding="utf-8")
    OUT_HORSE.write_text(build_mini_horse_race_table(horse_df), encoding="utf-8")

    print(f"Wrote {OUT_STATUS}")
    print(f"Wrote {OUT_AUDIT}")
    print(f"Wrote {OUT_ANCHOR_SAMPLE}")
    print(f"Wrote {OUT_ANCHOR_DESC}")
    print(f"Wrote {OUT_ANCHOR_FIRM}")
    print(f"Wrote {OUT_ANCHOR_USER}")
    print(f"Wrote {OUT_REDUCED1_FIRM}")
    print(f"Wrote {OUT_REDUCED1_USER}")
    print(f"Wrote {OUT_FIRM_GRID}")
    print(f"Wrote {OUT_USER_GRID}")
    print(f"Wrote {OUT_FIRM_MEASURE_SOFTWARE}")
    print(f"Wrote {OUT_FIRM_MEASURE_COUNT}")
    print(f"Wrote {OUT_FIRM_MEASURE_TOPQ}")
    print(f"Wrote {OUT_USER_MEASURE_SOFTWARE}")
    print(f"Wrote {OUT_USER_MEASURE_COUNT}")
    print(f"Wrote {OUT_USER_MEASURE_TOPQ}")
    print(f"Wrote {OUT_PAIR}")
    print(f"Wrote {OUT_HORSE_FIRM}")
    print(f"Wrote {OUT_HORSE}")


if __name__ == "__main__":
    main()
