#!/usr/bin/env python3
"""Build LaTeX tables for the LLM-equity CB analysis package.

This script produces:
  1) the original matched-vs-backfill tables (kept for diagnostics), and
  2) backfill-only variants (for write-ups that exclude the matched sample).
"""

from __future__ import annotations

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

LB: Final[str] = r" \\"
TOP: Final[str] = r"\toprule"
MID: Final[str] = r"\midrule"
BOTTOM: Final[str] = r"\bottomrule"
PREAMBLE: Final[str] = r"\centering"
INDENT: Final[str] = r"\hspace{1em}"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

FIRM_RAW: Final[Path] = RESULTS_RAW / "firm_scaling_llm_equity_cb_modes" / "consolidated_results.csv"
USER_RAW: Final[Path] = RESULTS_RAW / "user_productivity_llm_equity_cb_modes_precovid" / "consolidated_results.csv"
SAMPLE_RAW: Final[Path] = RESULTS_RAW / "llm_equity_cb_modes" / "sample_accounting.csv"
SHARES_RAW: Final[Path] = RESULTS_RAW / "llm_equity_cb_modes" / "startup_vs_nonstartup_equity_shares.csv"
SHARES_RAW_LEGACY: Final[Path] = RESULTS_RAW / "llm_equity_cb_modes" / "startup_vs_large_equity_shares.csv"
INTENSIVE_RAW: Final[Path] = RESULTS_RAW / "llm_equity_cb_modes" / "intensive_margin_summary.csv"

OUT_SAMPLE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_sample_accounting.tex"
OUT_DESC: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_descriptives.tex"

OUT_SAMPLE_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_sample_accounting.tex"
OUT_DESC_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_descriptives.tex"

OUT_FIRM_CORE_POOLED: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_core_pooled.tex"
OUT_FIRM_SPLIT_NON_EQ: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_core_split_non_equity.tex"
OUT_FIRM_SPLIT_EQ: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_core_split_equity.tex"
OUT_FIRM_INTENSIVE_SHARE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_intensive_share.tex"
OUT_FIRM_INTENSIVE_COUNT_MEAN: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_intensive_count_mean.tex"
OUT_FIRM_REDUCED1: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_reduced1.tex"
OUT_FIRM_SIMPLE_DD: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_simple_dd.tex"
OUT_FIRM_CONCENTRATION_ANY: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_concentration_any.tex"
OUT_FIRM_CONCENTRATION_SHARE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_concentration_share.tex"
OUT_FIRM_CONCENTRATION_COUNT_MEAN: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_firm_concentration_count_mean.tex"

OUT_FIRM_CORE_POOLED_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_firm_core_pooled.tex"
OUT_FIRM_SPLIT_NON_EQ_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_firm_core_split_non_equity.tex"
OUT_FIRM_SPLIT_EQ_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_firm_core_split_equity.tex"

OUT_USER_CORE_POOLED: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_core_pooled.tex"
OUT_USER_SPLIT_NON_EQ: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_core_split_non_equity.tex"
OUT_USER_SPLIT_EQ: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_core_split_equity.tex"
OUT_USER_INTENSIVE_SHARE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_intensive_share.tex"
OUT_USER_INTENSIVE_COUNT_MEAN: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_intensive_count_mean.tex"
OUT_USER_REDUCED1: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_reduced1.tex"
OUT_USER_SIMPLE_DD: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_simple_dd.tex"
OUT_USER_CONCENTRATION_ANY: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_concentration_any.tex"
OUT_USER_CONCENTRATION_SHARE: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_concentration_share.tex"
OUT_USER_CONCENTRATION_COUNT_MEAN: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_modes_user_concentration_count_mean.tex"

OUT_USER_CORE_POOLED_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_user_core_pooled.tex"
OUT_USER_SPLIT_NON_EQ_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_user_core_split_non_equity.tex"
OUT_USER_SPLIT_EQ_BACKFILL: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_cb_backfill_user_core_split_equity.tex"

COLUMNS_4: Final[list[tuple[str, str, str]]] = [
    ("matched", "OLS", "Matched OLS"),
    ("matched", "IV", "Matched IV"),
    ("backfill", "OLS", "Backfill OLS"),
    ("backfill", "IV", "Backfill IV"),
]

COLUMNS_2: Final[list[tuple[str, str, str]]] = [
    ("matched", "OLS", "Matched OLS"),
    ("backfill", "OLS", "Backfill OLS"),
]

PARAM_LABEL: Final[dict[str, str]] = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var3_eq_any": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityFirm} $",
    "var5_eq_any": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{EquityFirm} $",
    "eq_any_firm_covid": r"$ \text{EquityFirm} \times \mathds{1}(\text{Post}) $",
    "var3_eq_share": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityShare} $",
    "var5_eq_share": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{EquityShare} $",
    "eq_share_firm_covid": r"$ \text{EquityShare} \times \mathds{1}(\text{Post}) $",
    "var3_eq_count_mean": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{EquityCountMean} $",
    "var5_eq_count_mean": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} \times \text{EquityCountMean} $",
    "eq_count_mean_firm_covid": r"$ \text{EquityCountMean} \times \mathds{1}(\text{Post}) $",
}


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


def coef_cell(row: pd.Series | None) -> str:
    if row is None:
        return "--"
    coef = row.get("coef")
    se = row.get("se")
    pval = row.get("pval")
    if pd.isna(coef) or pd.isna(se):
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


def find_row(
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


def tabular(colspec: str, body_lines: list[str]) -> str:
    lines = [PREAMBLE, rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def column_format(n_numeric: int) -> str:
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"


def build_headers_4col() -> list[str]:
    return [
        r" & \multicolumn{2}{c}{Matched} & \multicolumn{2}{c}{Backfill}" + LB,
        r"\cmidrule(lr){2-3}",
        r"\cmidrule(lr){4-5}",
        " & OLS & IV & OLS & IV" + LB,
        " & (1) & (2) & (3) & (4)" + LB,
    ]


def build_headers_2col() -> list[str]:
    return [
        r" & \multicolumn{1}{c}{Matched} & \multicolumn{1}{c}{Backfill}" + LB,
        r"\cmidrule(lr){2-2}",
        r"\cmidrule(lr){3-3}",
        " & OLS & OLS" + LB,
        " & (1) & (2)" + LB,
    ]


def build_headers_backfill_ols_iv() -> list[str]:
    return [
        "Parameter & OLS & IV" + LB,
        " & (1) & (2)" + LB,
    ]


def regression_label(ols_only: bool, *, title: str) -> str:
    if ols_only:
        return title + " (OLS)"
    return title + " (OLS + IV)"


def fixed_effect_rows(*, include_users: bool, ncols: int) -> list[str]:
    checks = " & ".join([r"$\checkmark$"] * ncols)
    rows = [r"\textbf{Fixed Effects} & " + " & ".join([""] * ncols) + LB]
    if include_users:
        rows.append(INDENT + "Individual & " + checks + LB)
    rows.append(INDENT + "Firm & " + checks + LB)
    rows.append(INDENT + "Half-year & " + checks + LB)
    return rows


def reference_row_for_stats(
    df: pd.DataFrame,
    *,
    sample_mode: str,
    model_type: str,
    outcome: str,
    analysis_block: str,
    equity_measure: str,
    split_group: str,
    params: list[str],
) -> pd.Series | None:
    for param in params:
        row = find_row(
            df,
            sample_mode=sample_mode,
            analysis_block=analysis_block,
            equity_measure=equity_measure,
            split_group=split_group,
            model_type=model_type,
            outcome=outcome,
            param=param,
        )
        if row is not None:
            return row
    return None


def build_regression_table(
    df: pd.DataFrame,
    *,
    outcome: str,
    analysis_block: str,
    equity_measure: str,
    split_group: str,
    params: list[str],
    include_users: bool,
    title: str,
    ols_only: bool = False,
) -> str:
    columns = COLUMNS_2 if ols_only else COLUMNS_4
    header_rows = build_headers_2col() if ols_only else build_headers_4col()
    n_numeric = 2 if ols_only else 4
    n_total_cols = n_numeric + 1
    lines: list[str] = [
        *header_rows,
        MID,
        rf"\multicolumn{{{n_total_cols}}}{{@{{}}l}}{{\textbf{{\uline{{{regression_label(ols_only, title=title)}}}}}}} "
        + LB,
        r"\addlinespace[2pt]",
    ]

    for param in params:
        row = [INDENT + PARAM_LABEL.get(param, param)]
        for sample_mode, model_type, _ in columns:
            rec = find_row(
                df,
                sample_mode=sample_mode,
                analysis_block=analysis_block,
                equity_measure=equity_measure,
                split_group=split_group,
                model_type=model_type,
                outcome=outcome,
                param=param,
            )
            row.append(coef_cell(rec))
        lines.append(" & ".join(row) + LB)

    pre_row = ["Pre-Covid Mean"]
    rkf_row = ["KP rk Wald F"]
    n_row = ["N"]
    firms_row = ["Firms"]
    users_row = ["Users"]
    for sample_mode, model_type, _ in columns:
        ref = reference_row_for_stats(
            df,
            sample_mode=sample_mode,
            model_type=model_type,
            outcome=outcome,
            analysis_block=analysis_block,
            equity_measure=equity_measure,
            split_group=split_group,
            params=params,
        )
        pre_row.append(stat_cell(ref, "pre_mean", "{:.2f}"))
        if not ols_only:
            rkf_row.append(stat_cell(ref, "rkf", "{:.2f}") if model_type == "IV" else "")
        n_row.append(stat_cell(ref, "nobs", "{:,.0f}"))
        firms_row.append(stat_cell(ref, "n_firms", "{:,.0f}"))
        users_row.append(stat_cell(ref, "n_users", "{:,.0f}"))

    lines.extend([MID, " & ".join(pre_row) + LB])
    if not ols_only:
        lines.append(" & ".join(rkf_row) + LB)
    lines.extend([" & ".join(n_row) + LB, " & ".join(firms_row) + LB])
    if include_users:
        lines.append(" & ".join(users_row) + LB)
    lines.extend([MID, *fixed_effect_rows(include_users=include_users, ncols=n_numeric)])
    return tabular(column_format(n_numeric), lines)


def build_regression_table_backfill_only(
    df: pd.DataFrame,
    *,
    outcome: str,
    analysis_block: str,
    equity_measure: str,
    split_group: str,
    params: list[str],
    include_users: bool,
    title: str,
) -> str:
    header_rows = build_headers_backfill_ols_iv()
    n_numeric = 2
    n_total_cols = n_numeric + 1
    lines: list[str] = [
        *header_rows,
        MID,
        rf"\multicolumn{{{n_total_cols}}}{{@{{}}l}}{{\textbf{{\uline{{{regression_label(False, title=title)}}}}}}} "
        + LB,
        r"\addlinespace[2pt]",
    ]

    for param in params:
        row = [INDENT + PARAM_LABEL.get(param, param)]
        for model_type in ["OLS", "IV"]:
            rec = find_row(
                df,
                sample_mode="backfill",
                analysis_block=analysis_block,
                equity_measure=equity_measure,
                split_group=split_group,
                model_type=model_type,
                outcome=outcome,
                param=param,
            )
            row.append(coef_cell(rec))
        lines.append(" & ".join(row) + LB)

    ref_ols = reference_row_for_stats(
        df,
        sample_mode="backfill",
        model_type="OLS",
        outcome=outcome,
        analysis_block=analysis_block,
        equity_measure=equity_measure,
        split_group=split_group,
        params=params,
    )
    ref_iv = reference_row_for_stats(
        df,
        sample_mode="backfill",
        model_type="IV",
        outcome=outcome,
        analysis_block=analysis_block,
        equity_measure=equity_measure,
        split_group=split_group,
        params=params,
    )

    pre_row = ["Pre-Covid Mean", stat_cell(ref_ols, "pre_mean", "{:.2f}"), stat_cell(ref_iv, "pre_mean", "{:.2f}")]
    rkf_row = ["KP rk Wald F", "", stat_cell(ref_iv, "rkf", "{:.2f}")]
    n_row = ["N", stat_cell(ref_ols, "nobs", "{:,.0f}"), stat_cell(ref_iv, "nobs", "{:,.0f}")]
    firms_row = ["Firms", stat_cell(ref_ols, "n_firms", "{:,.0f}"), stat_cell(ref_iv, "n_firms", "{:,.0f}")]
    users_row = ["Users", stat_cell(ref_ols, "n_users", "{:,.0f}"), stat_cell(ref_iv, "n_users", "{:,.0f}")]

    lines.extend([MID, " & ".join(pre_row) + LB, " & ".join(rkf_row) + LB])
    lines.extend([" & ".join(n_row) + LB, " & ".join(firms_row) + LB])
    if include_users:
        lines.append(" & ".join(users_row) + LB)
    lines.extend([MID, *fixed_effect_rows(include_users=include_users, ncols=n_numeric)])
    return tabular(column_format(n_numeric), lines)


def build_sample_accounting_table(sample_df: pd.DataFrame) -> str:
    cols = ["Sample", "Rows", "Firms", "Parse rows", "Startup firms", "Non-startup firms", "Equity firms"]
    mode_label = {"matched": "Matched", "backfill": "Backfill"}
    nonstartup_col = "n_nonstartup_firms" if "n_nonstartup_firms" in sample_df.columns else "n_large_firms"
    lines: list[str] = [" & ".join(cols) + LB, MID]
    for mode in ["matched", "backfill"]:
        sub = sample_df[sample_df["sample_mode"] == mode].head(1)
        if sub.empty:
            continue
        r = sub.iloc[0]
        lines.append(
            " & ".join(
                [
                    mode_label.get(mode, mode),
                    f"{int(r['n_rows']):,}",
                    f"{int(r['n_firms']):,}",
                    f"{int(r['n_rows_parse_ok']):,}",
                    f"{int(r['n_startup_firms']):,}",
                    f"{int(r[nonstartup_col]):,}",
                    f"{int(r['n_firms_equity_any']):,}",
                ]
            )
            + LB
        )
    return tabular(r"@{}l@{\extracolsep{\fill}}cccccc@{}", lines)


def build_sample_accounting_table_backfill_only(sample_df: pd.DataFrame) -> str:
    cols = ["Sample", "Rows", "Firms", "Parse rows", "Startup firms", "Non-startup firms", "Equity firms"]
    nonstartup_col = "n_nonstartup_firms" if "n_nonstartup_firms" in sample_df.columns else "n_large_firms"
    lines: list[str] = [" & ".join(cols) + LB, MID]
    sub = sample_df[sample_df["sample_mode"] == "backfill"].head(1)
    if not sub.empty:
        r = sub.iloc[0]
        lines.append(
            " & ".join(
                [
                    "Backfill",
                    f"{int(r['n_rows']):,}",
                    f"{int(r['n_firms']):,}",
                    f"{int(r['n_rows_parse_ok']):,}",
                    f"{int(r['n_startup_firms']):,}",
                    f"{int(r[nonstartup_col]):,}",
                    f"{int(r['n_firms_equity_any']):,}",
                ]
            )
            + LB
        )
    return tabular(r"@{}l@{\extracolsep{\fill}}cccccc@{}", lines)


def build_descriptives_table(shares_df: pd.DataFrame, intensive_df: pd.DataFrame) -> str:
    merged = shares_df.merge(intensive_df, on=["sample_mode", "firm_group", "n_firms"], how="outer")
    merged["firm_group"] = merged["firm_group"].map({"startup": "Startup", "non_startup": "Non-startup", "large": "Non-startup"})
    merged["sample_mode"] = merged["sample_mode"].map({"matched": "Matched", "backfill": "Backfill"})

    headers = ["Sample", "Firm group", "Firms", r"\% any equity", "Mean share", "Median share", "Mean count", "Median count"]
    lines: list[str] = [" & ".join(headers) + LB, MID]
    for sample in ["Matched", "Backfill"]:
        for group in ["Startup", "Non-startup"]:
            sub = merged[(merged["sample_mode"] == sample) & (merged["firm_group"] == group)].head(1)
            if sub.empty:
                continue
            r = sub.iloc[0]
            pct = r.get("pct_equity_any")
            mshare = r.get("mean_eq_share_firm")
            p50share = r.get("median_eq_share_firm")
            mcount = r.get("mean_eq_count_firm")
            p50count = r.get("median_eq_count_firm")
            lines.append(
                " & ".join(
                    [
                        sample,
                        group,
                        f"{int(r['n_firms']):,}",
                        "--" if pd.isna(pct) else f"{100.0 * float(pct):.1f}",
                        "--" if pd.isna(mshare) else f"{float(mshare):.3f}",
                        "--" if pd.isna(p50share) else f"{float(p50share):.3f}",
                        "--" if pd.isna(mcount) else f"{float(mcount):.3f}",
                        "--" if pd.isna(p50count) else f"{float(p50count):.3f}",
                    ]
                )
                + LB
            )
    return tabular(r"@{}l@{\extracolsep{\fill}}ccccccc@{}", lines)


def build_descriptives_table_backfill_only(shares_df: pd.DataFrame, intensive_df: pd.DataFrame) -> str:
    merged = shares_df.merge(intensive_df, on=["sample_mode", "firm_group", "n_firms"], how="outer")
    merged["firm_group"] = merged["firm_group"].map({"startup": "Startup", "non_startup": "Non-startup", "large": "Non-startup"})
    merged["sample_mode"] = merged["sample_mode"].map({"matched": "Matched", "backfill": "Backfill"})

    headers = ["Sample", "Firm group", "Firms", r"\% any equity", "Mean share", "Median share", "Mean count", "Median count"]
    lines: list[str] = [" & ".join(headers) + LB, MID]
    for group in ["Startup", "Non-startup"]:
        sub = merged[(merged["sample_mode"] == "Backfill") & (merged["firm_group"] == group)].head(1)
        if sub.empty:
            continue
        r = sub.iloc[0]
        pct = r.get("pct_equity_any")
        mshare = r.get("mean_eq_share_firm")
        p50share = r.get("median_eq_share_firm")
        mcount = r.get("mean_eq_count_firm")
        p50count = r.get("median_eq_count_firm")
        lines.append(
            " & ".join(
                [
                    "Backfill",
                    group,
                    f"{int(r['n_firms']):,}",
                    "--" if pd.isna(pct) else f"{100.0 * float(pct):.1f}",
                    "--" if pd.isna(mshare) else f"{float(mshare):.3f}",
                    "--" if pd.isna(p50share) else f"{float(p50share):.3f}",
                    "--" if pd.isna(mcount) else f"{float(mcount):.3f}",
                    "--" if pd.isna(p50count) else f"{float(p50count):.3f}",
                ]
            )
            + LB
        )
    return tabular(r"@{}l@{\extracolsep{\fill}}ccccccc@{}", lines)


def main() -> None:
    shares_path = SHARES_RAW if SHARES_RAW.exists() else SHARES_RAW_LEGACY
    for path, purpose in [
        (FIRM_RAW, "firm CB-modes regression results"),
        (USER_RAW, "user CB-modes regression results"),
        (SAMPLE_RAW, "CB-modes sample accounting"),
        (shares_path, "CB-modes startup/non-startup equity shares"),
        (INTENSIVE_RAW, "CB-modes intensive margin summary"),
    ]:
        require_file(path, nonempty=True, purpose=purpose)

    firm_df = pd.read_csv(FIRM_RAW)
    user_df = pd.read_csv(USER_RAW)
    sample_df = pd.read_csv(SAMPLE_RAW)
    shares_df = pd.read_csv(shares_path)
    intensive_df = pd.read_csv(INTENSIVE_RAW)

    ensure_dir(RESULTS_CLEANED_TEX)
    OUT_SAMPLE.write_text(build_sample_accounting_table(sample_df), encoding="utf-8")
    OUT_DESC.write_text(build_descriptives_table(shares_df, intensive_df), encoding="utf-8")
    OUT_SAMPLE_BACKFILL.write_text(build_sample_accounting_table_backfill_only(sample_df), encoding="utf-8")
    OUT_DESC_BACKFILL.write_text(build_descriptives_table_backfill_only(shares_df, intensive_df), encoding="utf-8")

    firm_specs = [
        (
            OUT_FIRM_CORE_POOLED,
            "core_pooled",
            "any",
            "all",
            ["var3", "var5", "var3_eq_any", "var5_eq_any", "eq_any_firm_covid"],
            "Core pooled (extensive margin)",
            False,
        ),
        (
            OUT_FIRM_SPLIT_NON_EQ,
            "core_split",
            "any",
            "eq_any_firm_0",
            ["var3", "var5"],
            "Core split: non-equity firms",
            False,
        ),
        (
            OUT_FIRM_SPLIT_EQ,
            "core_split",
            "any",
            "eq_any_firm_1",
            ["var3", "var5"],
            "Core split: equity firms",
            False,
        ),
        (
            OUT_FIRM_INTENSIVE_SHARE,
            "intensive_share",
            "share",
            "all",
            ["var3", "var5", "var3_eq_share", "var5_eq_share", "eq_share_firm_covid"],
            "Intensive margin: equity share",
            False,
        ),
        (
            OUT_FIRM_INTENSIVE_COUNT_MEAN,
            "intensive_count",
            "count_mean",
            "all",
            ["var3", "var5", "var3_eq_count_mean", "var5_eq_count_mean", "eq_count_mean_firm_covid"],
            "Intensive margin: equity count mean",
            False,
        ),
        (
            OUT_FIRM_REDUCED1,
            "reduced1",
            "any",
            "all",
            ["var3", "var3_eq_any", "eq_any_firm_covid"],
            "Reduced-1: Remote DD + equity heterogeneity (no startup interaction)",
            False,
        ),
        (
            OUT_FIRM_SIMPLE_DD,
            "reduced2",
            "any",
            "all",
            ["var3"],
            "Reduced-2: Remote × Post only DD",
            False,
        ),
        (
            OUT_FIRM_CONCENTRATION_ANY,
            "concentration",
            "any",
            "all",
            ["eq_any_firm_covid"],
            "Concentration OLS: Equity exposure × Post (extensive margin)",
            True,
        ),
        (
            OUT_FIRM_CONCENTRATION_SHARE,
            "concentration",
            "share",
            "all",
            ["eq_share_firm_covid"],
            "Concentration OLS: Equity exposure × Post (share intensity)",
            True,
        ),
        (
            OUT_FIRM_CONCENTRATION_COUNT_MEAN,
            "concentration",
            "count_mean",
            "all",
            ["eq_count_mean_firm_covid"],
            "Concentration OLS: Equity exposure × Post (count intensity)",
            True,
        ),
    ]

    for out_path, block, measure, split, params, title, ols_only in firm_specs:
        out_path.write_text(
            build_regression_table(
                firm_df,
                outcome="growth_rate_we",
                analysis_block=block,
                equity_measure=measure,
                split_group=split,
                params=params,
                include_users=False,
                title=title,
                ols_only=ols_only,
            ),
            encoding="utf-8",
        )

    # Backfill-only core tables (exclude matched sample)
    OUT_FIRM_CORE_POOLED_BACKFILL.write_text(
        build_regression_table_backfill_only(
            firm_df,
            outcome="growth_rate_we",
            analysis_block="core_pooled",
            equity_measure="any",
            split_group="all",
            params=["var3", "var5", "var3_eq_any", "var5_eq_any", "eq_any_firm_covid"],
            include_users=False,
            title="Core pooled (extensive margin)",
        ),
        encoding="utf-8",
    )
    OUT_FIRM_SPLIT_NON_EQ_BACKFILL.write_text(
        build_regression_table_backfill_only(
            firm_df,
            outcome="growth_rate_we",
            analysis_block="core_split",
            equity_measure="any",
            split_group="eq_any_firm_0",
            params=["var3", "var5"],
            include_users=False,
            title="Core split: non-equity firms",
        ),
        encoding="utf-8",
    )
    OUT_FIRM_SPLIT_EQ_BACKFILL.write_text(
        build_regression_table_backfill_only(
            firm_df,
            outcome="growth_rate_we",
            analysis_block="core_split",
            equity_measure="any",
            split_group="eq_any_firm_1",
            params=["var3", "var5"],
            include_users=False,
            title="Core split: equity firms",
        ),
        encoding="utf-8",
    )

    user_specs = [
        (
            OUT_USER_CORE_POOLED,
            "core_pooled",
            "any",
            "all",
            ["var3", "var5", "var3_eq_any", "var5_eq_any", "eq_any_firm_covid"],
            "Core pooled (extensive margin)",
            False,
        ),
        (
            OUT_USER_SPLIT_NON_EQ,
            "core_split",
            "any",
            "eq_any_firm_0",
            ["var3", "var5"],
            "Core split: non-equity firms",
            False,
        ),
        (
            OUT_USER_SPLIT_EQ,
            "core_split",
            "any",
            "eq_any_firm_1",
            ["var3", "var5"],
            "Core split: equity firms",
            False,
        ),
        (
            OUT_USER_INTENSIVE_SHARE,
            "intensive_share",
            "share",
            "all",
            ["var3", "var5", "var3_eq_share", "var5_eq_share", "eq_share_firm_covid"],
            "Intensive margin: equity share",
            False,
        ),
        (
            OUT_USER_INTENSIVE_COUNT_MEAN,
            "intensive_count",
            "count_mean",
            "all",
            ["var3", "var5", "var3_eq_count_mean", "var5_eq_count_mean", "eq_count_mean_firm_covid"],
            "Intensive margin: equity count mean",
            False,
        ),
        (
            OUT_USER_REDUCED1,
            "reduced1",
            "any",
            "all",
            ["var3", "var3_eq_any", "eq_any_firm_covid"],
            "Reduced-1: Remote DD + equity heterogeneity (no startup interaction)",
            False,
        ),
        (
            OUT_USER_SIMPLE_DD,
            "reduced2",
            "any",
            "all",
            ["var3"],
            "Reduced-2: Remote × Post only DD",
            False,
        ),
        (
            OUT_USER_CONCENTRATION_ANY,
            "concentration",
            "any",
            "all",
            ["eq_any_firm_covid"],
            "Concentration OLS: Equity exposure × Post (extensive margin)",
            True,
        ),
        (
            OUT_USER_CONCENTRATION_SHARE,
            "concentration",
            "share",
            "all",
            ["eq_share_firm_covid"],
            "Concentration OLS: Equity exposure × Post (share intensity)",
            True,
        ),
        (
            OUT_USER_CONCENTRATION_COUNT_MEAN,
            "concentration",
            "count_mean",
            "all",
            ["eq_count_mean_firm_covid"],
            "Concentration OLS: Equity exposure × Post (count intensity)",
            True,
        ),
    ]

    for out_path, block, measure, split, params, title, ols_only in user_specs:
        out_path.write_text(
            build_regression_table(
                user_df,
                outcome="total_contributions_q100",
                analysis_block=block,
                equity_measure=measure,
                split_group=split,
                params=params,
                include_users=True,
                title=title,
                ols_only=ols_only,
            ),
            encoding="utf-8",
        )

    OUT_USER_CORE_POOLED_BACKFILL.write_text(
        build_regression_table_backfill_only(
            user_df,
            outcome="total_contributions_q100",
            analysis_block="core_pooled",
            equity_measure="any",
            split_group="all",
            params=["var3", "var5", "var3_eq_any", "var5_eq_any", "eq_any_firm_covid"],
            include_users=True,
            title="Core pooled (extensive margin)",
        ),
        encoding="utf-8",
    )
    OUT_USER_SPLIT_NON_EQ_BACKFILL.write_text(
        build_regression_table_backfill_only(
            user_df,
            outcome="total_contributions_q100",
            analysis_block="core_split",
            equity_measure="any",
            split_group="eq_any_firm_0",
            params=["var3", "var5"],
            include_users=True,
            title="Core split: non-equity firms",
        ),
        encoding="utf-8",
    )
    OUT_USER_SPLIT_EQ_BACKFILL.write_text(
        build_regression_table_backfill_only(
            user_df,
            outcome="total_contributions_q100",
            analysis_block="core_split",
            equity_measure="any",
            split_group="eq_any_firm_1",
            params=["var3", "var5"],
            include_users=True,
            title="Core split: equity firms",
        ),
        encoding="utf-8",
    )

    written = [
        OUT_SAMPLE,
        OUT_DESC,
        OUT_SAMPLE_BACKFILL,
        OUT_DESC_BACKFILL,
        OUT_FIRM_CORE_POOLED,
        OUT_FIRM_SPLIT_NON_EQ,
        OUT_FIRM_SPLIT_EQ,
        OUT_FIRM_INTENSIVE_SHARE,
        OUT_FIRM_INTENSIVE_COUNT_MEAN,
        OUT_FIRM_REDUCED1,
        OUT_FIRM_SIMPLE_DD,
        OUT_FIRM_CONCENTRATION_ANY,
        OUT_FIRM_CONCENTRATION_SHARE,
        OUT_FIRM_CONCENTRATION_COUNT_MEAN,
        OUT_USER_CORE_POOLED,
        OUT_USER_SPLIT_NON_EQ,
        OUT_USER_SPLIT_EQ,
        OUT_USER_INTENSIVE_SHARE,
        OUT_USER_INTENSIVE_COUNT_MEAN,
        OUT_USER_REDUCED1,
        OUT_USER_SIMPLE_DD,
        OUT_USER_CONCENTRATION_ANY,
        OUT_USER_CONCENTRATION_SHARE,
        OUT_USER_CONCENTRATION_COUNT_MEAN,
        OUT_FIRM_CORE_POOLED_BACKFILL,
        OUT_FIRM_SPLIT_NON_EQ_BACKFILL,
        OUT_FIRM_SPLIT_EQ_BACKFILL,
        OUT_USER_CORE_POOLED_BACKFILL,
        OUT_USER_SPLIT_NON_EQ_BACKFILL,
        OUT_USER_SPLIT_EQ_BACKFILL,
    ]
    for out_path in written:
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
