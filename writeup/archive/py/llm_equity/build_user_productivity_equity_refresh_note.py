#!/usr/bin/env python3
"""Build a user-productivity-only LaTeX note for refreshed LLM-equity results."""

from __future__ import annotations

import math
import sys
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
PREAMBLE: Final[str] = r"\centering"

STAR_RULES: Final[list[tuple[float, str]]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

USER_PANEL: Final[Path] = DATA_CLEAN / "user_panel_precovid.dta"
ENRICHED_PANEL: Final[Path] = (
    RESULTS_RAW / "postings_description_equity" / "firm_merge" / "latest_firm_yh_llm_equity_enriched.csv"
)
NO_CB_USER_RAW: Final[Path] = RESULTS_RAW / "user_productivity_llm_equity_no_cb_modes_precovid" / "consolidated_results.csv"
PAIR_REPLACE_RAW: Final[Path] = (
    RESULTS_RAW / "user_productivity_llm_equity_replace_startup_pair_fe_precovid" / "consolidated_results.csv"
)
HORSE_RACE_RAW: Final[Path] = RESULTS_RAW / "user_horse_race_equity_precovid" / "consolidated_results.csv"
PAIR_HORSE_RACE_RAW: Final[Path] = RESULTS_RAW / "user_horse_race_equity_pair_fe_precovid" / "consolidated_results.csv"

OUT_DATA_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_refresh_data_overview.tex"
OUT_REPLACE_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_refresh_replace_startup_equity.tex"
OUT_HORSE_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_refresh_horse_race.tex"
OUT_PAIR_HORSE_TEX: Final[Path] = RESULTS_CLEANED_TEX / "llm_equity_user_refresh_horse_race_pairfe.tex"
OUT_NOTE_TEX: Final[Path] = PROJECT_ROOT / "writeup" / "tex" / "llm_equity_user_productivity_refresh_note.tex"


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


def fmt_pct(value: float | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "--"
    return f"{100.0 * float(value):.{digits}f}\\%"


def coef_cell(row: pd.Series | None) -> str:
    if row is None:
        return "--"
    coef = row.get("coef")
    se = row.get("se")
    pval = row.get("pval")
    if coef is None or se is None or pd.isna(coef) or pd.isna(se) or float(se) == 0.0:
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


def tabular_star(colspec: str, body_lines: list[str]) -> str:
    lines = [PREAMBLE, rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}", TOP]
    lines.extend(body_lines)
    lines.extend([BOTTOM, r"\end{tabular*}"])
    return "\n".join(lines) + "\n"


def _row(df: pd.DataFrame, **filters: object) -> pd.Series | None:
    mask = pd.Series(True, index=df.index)
    for col, value in filters.items():
        mask &= df[col] == value
    hit = df.loc[mask].head(1)
    if hit.empty:
        return None
    return hit.iloc[0]


def build_data_overview_table() -> str:
    user = pd.read_stata(
        require_file(USER_PANEL, nonempty=True, purpose="user_panel_precovid.dta"),
        columns=["user_id", "firm_id", "companyname", "yh", "startup"],
        convert_categoricals=False,
    )
    user["startup"] = user["startup"].fillna(0).astype(int)
    user["firm_id_key"] = user["companyname"].astype(str).str.strip().str.lower()

    cells = user[["firm_id", "firm_id_key", "yh", "startup"]].drop_duplicates().copy()
    if not pd.api.types.is_datetime64_any_dtype(cells["yh"]):
        raise RuntimeError("Expected user-panel yh to be parsed as datetime64.")

    usecols = [
        "firm_id_key",
        "yh",
        "n_postings_desc_total",
        "n_keyword_hit_candidates",
        "n_llm_target_postings",
        "llm_n_equity_true_raw",
        "llm_equity_any_raw",
    ]
    equity = pd.read_csv(require_file(ENRICHED_PANEL, nonempty=True, purpose="latest enriched equity panel"), usecols=usecols)
    equity["firm_id_key"] = equity["firm_id_key"].astype(str).str.strip().str.lower()
    equity["yh"] = pd.to_datetime(equity["yh"], errors="coerce")
    equity = equity.dropna(subset=["firm_id_key", "yh"]).drop_duplicates(subset=["firm_id_key", "yh"])

    merged = cells.merge(equity, on=["firm_id_key", "yh"], how="left", validate="m:1")
    for col in [
        "n_postings_desc_total",
        "n_keyword_hit_candidates",
        "n_llm_target_postings",
        "llm_n_equity_true_raw",
        "llm_equity_any_raw",
    ]:
        merged[col] = merged[col].fillna(0)

    firm = (
        merged.groupby(["firm_id", "startup"], as_index=False)
        .agg(
            equity_firm=("llm_equity_any_raw", lambda s: int((s > 0).any())),
            postings=("n_postings_desc_total", "sum"),
            keyword=("n_keyword_hit_candidates", "sum"),
            llm_target=("n_llm_target_postings", "sum"),
            llm_equity=("llm_n_equity_true_raw", "sum"),
        )
    )

    def _panel_mask(startup_value: int | None) -> pd.Series:
        if startup_value is None:
            return pd.Series(True, index=merged.index)
        return merged["startup"] == startup_value

    def _firm_mask(startup_value: int | None) -> pd.Series:
        if startup_value is None:
            return pd.Series(True, index=firm.index)
        return firm["startup"] == startup_value

    cols: list[tuple[str, int | None]] = [("All", None), ("Startups", 1), ("Non-startups", 0)]
    values: dict[str, list[str]] = {
        "User-half-year rows": [],
        "Firm$\\times$half-year cells": [],
        "Firms": [],
        "Firms offering equity (any half-year)": [],
        "Share of firms offering equity": [],
        "Postings with descriptions (sum)": [],
        "Offers-equity postings (LLM sum)": [],
        "Share of postings offering equity (LLM)": [],
    }

    for _, g in cols:
        pmask = _panel_mask(g)
        fmask = _firm_mask(g)
        postings = float(merged.loc[pmask, "n_postings_desc_total"].sum())
        llm_equity = float(merged.loc[pmask, "llm_n_equity_true_raw"].sum())
        n_firms = int(firm.loc[fmask].shape[0])
        n_equity_firms = int(firm.loc[fmask, "equity_firm"].sum())

        values["User-half-year rows"].append(fmt_int(int(user.loc[user["startup"] == g].shape[0]) if g is not None else int(user.shape[0])))
        values["Firm$\\times$half-year cells"].append(fmt_int(int(merged.loc[pmask].shape[0])))
        values["Firms"].append(fmt_int(n_firms))
        values["Firms offering equity (any half-year)"].append(fmt_int(n_equity_firms))
        values["Share of firms offering equity"].append(fmt_pct((n_equity_firms / n_firms) if n_firms else float("nan")))
        values["Postings with descriptions (sum)"].append(fmt_int(postings))
        values["Offers-equity postings (LLM sum)"].append(fmt_int(llm_equity))
        values["Share of postings offering equity (LLM)"].append(fmt_pct((llm_equity / postings) if postings > 0 else float("nan")))

    lines = [
        r" & All & Startups & Non-startups" + LB,
        MID,
        r"\multicolumn{4}{@{}l}{\textbf{\uline{Panel A: Analysis universe}}}" + LB,
        r"\addlinespace[2pt]",
        rf"{INDENT}User-half-year rows & {' & '.join(values['User-half-year rows'])}" + LB,
        rf"{INDENT}Firm$\times$half-year cells & {' & '.join(values['Firm$\\times$half-year cells'])}" + LB,
        rf"{INDENT}Firms & {' & '.join(values['Firms'])}" + LB,
        MID,
        r"\multicolumn{4}{@{}l}{\textbf{\uline{Panel B: Equity signal support}}}" + LB,
        r"\addlinespace[2pt]",
        rf"{INDENT}Firms offering equity (any half-year) & {' & '.join(values['Firms offering equity (any half-year)'])}" + LB,
        rf"{INDENT}Share of firms offering equity & {' & '.join(values['Share of firms offering equity'])}" + LB,
        rf"{INDENT}Postings with descriptions (sum) & {' & '.join(values['Postings with descriptions (sum)'])}" + LB,
        rf"{INDENT}Offers-equity postings (LLM sum) & {' & '.join(values['Offers-equity postings (LLM sum)'])}" + LB,
        rf"{INDENT}Share of postings offering equity (LLM) & {' & '.join(values['Share of postings offering equity (LLM)'])}" + LB,
    ]
    return tabular_star(r"@{}l@{\extracolsep{\fill}}r@{\extracolsep{\fill}}r@{\extracolsep{\fill}}r@{}", lines)


def build_replace_startup_table(baseline_df: pd.DataFrame, pair_df: pd.DataFrame) -> str:
    params = [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var3_eq_any", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Offers equity} $"),
        ("eq_any_firm_covid", r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) $"),
    ]

    lines = [
        r" & \multicolumn{2}{c}{Baseline FE} & \multicolumn{2}{c}{Pair FE}" + LB,
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        "Parameter & OLS & IV & OLS & IV" + LB,
        " & (1) & (2) & (3) & (4)" + LB,
        MID,
    ]
    for param, label in params:
        row_ols = _row(
            baseline_df,
            sample_mode="backfill",
            analysis_block="reduced1",
            equity_measure="any",
            split_group="all",
            model_type="OLS",
            outcome="total_contributions_q100",
            param=param,
        )
        row_iv = _row(
            baseline_df,
            sample_mode="backfill",
            analysis_block="reduced1",
            equity_measure="any",
            split_group="all",
            model_type="IV",
            outcome="total_contributions_q100",
            param=param,
        )
        pair_ols = _row(
            pair_df,
            sample_mode="backfill",
            analysis_block="reduced1",
            equity_measure="any",
            split_group="all",
            model_type="OLS",
            outcome="total_contributions_q100",
            param=param,
        )
        pair_iv = _row(
            pair_df,
            sample_mode="backfill",
            analysis_block="reduced1",
            equity_measure="any",
            split_group="all",
            model_type="IV",
            outcome="total_contributions_q100",
            param=param,
        )
        lines.append(
            INDENT
            + label
            + " & "
            + coef_cell(row_ols)
            + " & "
            + coef_cell(row_iv)
            + " & "
            + coef_cell(pair_ols)
            + " & "
            + coef_cell(pair_iv)
            + LB
        )

    ref_ols = _row(
        baseline_df,
        sample_mode="backfill",
        analysis_block="reduced1",
        equity_measure="any",
        split_group="all",
        model_type="OLS",
        outcome="total_contributions_q100",
        param="var3",
    )
    ref_iv = _row(
        baseline_df,
        sample_mode="backfill",
        analysis_block="reduced1",
        equity_measure="any",
        split_group="all",
        model_type="IV",
        outcome="total_contributions_q100",
        param="var3",
    )
    pair_ref_ols = _row(
        pair_df,
        sample_mode="backfill",
        analysis_block="reduced1",
        equity_measure="any",
        split_group="all",
        model_type="OLS",
        outcome="total_contributions_q100",
        param="var3",
    )
    pair_ref_iv = _row(
        pair_df,
        sample_mode="backfill",
        analysis_block="reduced1",
        equity_measure="any",
        split_group="all",
        model_type="IV",
        outcome="total_contributions_q100",
        param="var3",
    )
    lines.extend(
        [
            MID,
            "Pre-shift mean & "
            + stat_cell(ref_ols, "pre_mean", "{:.2f}")
            + " & "
            + stat_cell(ref_iv, "pre_mean", "{:.2f}")
            + " & "
            + stat_cell(pair_ref_ols, "pre_mean", "{:.2f}")
            + " & "
            + stat_cell(pair_ref_iv, "pre_mean", "{:.2f}")
            + LB,
            "KP rk Wald F &  & "
            + stat_cell(ref_iv, "rkf", "{:.2f}")
            + " &  & "
            + stat_cell(pair_ref_iv, "rkf", "{:.2f}")
            + LB,
            "N & "
            + stat_cell(ref_ols, "nobs")
            + " & "
            + stat_cell(ref_iv, "nobs")
            + " & "
            + stat_cell(pair_ref_ols, "nobs")
            + " & "
            + stat_cell(pair_ref_iv, "nobs")
            + LB,
            "Firms & "
            + stat_cell(ref_ols, "n_firms")
            + " & "
            + stat_cell(ref_iv, "n_firms")
            + " & "
            + stat_cell(pair_ref_ols, "n_firms")
            + " & "
            + stat_cell(pair_ref_iv, "n_firms")
            + LB,
            "Users & "
            + stat_cell(ref_ols, "n_users")
            + " & "
            + stat_cell(ref_iv, "n_users")
            + " & "
            + stat_cell(pair_ref_ols, "n_users")
            + " & "
            + stat_cell(pair_ref_iv, "n_users")
            + LB,
            MID,
            r"\textbf{Fixed Effects} &  &  &  & " + LB,
            INDENT + r"Individual & $\checkmark$ & $\checkmark$ &  & " + LB,
            INDENT + r"Firm & $\checkmark$ & $\checkmark$ &  & " + LB,
            INDENT + r"Firm $\times$ individual &  &  & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Half-year & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
        ]
    )
    return tabular_star(
        r"@{}l@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{\extracolsep{\fill}}c@{}",
        lines,
    )


def build_horse_race_table(df: pd.DataFrame) -> str:
    spec_order = ["baseline", "labor_scaling", "equity_comp", "labor_scaling_equity_comp"]
    spec_titles = ["Baseline", "Labor scaling", "Equity offer", "Both"]
    core_labels = {
        "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
        "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    }
    control_labels = {
        "hr_scale_covid": r"$ \text{Labor scaling} \times \mathds{1}(\text{Post}) $",
        "hr_scale_covid_s": r"$ \text{Labor scaling} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
        "hr_eq_covid": r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) $",
        "hr_eq_covid_s": r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    }
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * len(spec_order) + "@{}"
    lines = [
        rf" & \multicolumn{{{len(spec_order)}}}{{c}}{{Contribution Rank}}" + LB,
        rf"\cmidrule(lr){{2-{len(spec_order) + 1}}}",
        " & " + " & ".join(f"({i})" for i in range(1, len(spec_order) + 1)) + LB,
        " & " + " & ".join(spec_titles) + LB,
        MID,
        rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}}" + LB,
        r"\addlinespace[2pt]",
    ]
    for param in ["var3", "var5"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textit{{Added controls}}}}" + LB,
        ]
    )
    for param in ["hr_scale_covid", "hr_scale_covid_s", "hr_eq_covid", "hr_eq_covid_s"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + control_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="OLS", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            MID,
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in ["var3", "var5"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textit{{Added controls}}}}" + LB,
        ]
    )
    for param in ["hr_scale_covid", "hr_scale_covid_s", "hr_eq_covid", "hr_eq_covid_s"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + control_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            r"KP\,rk Wald F & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "rkf", "{:.2f}") for spec in spec_order) + LB,
            MID,
            r"\textbf{Fixed Effects} &  &  &  & " + LB,
            INDENT + r"Individual & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Firm & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Half-year & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            MID,
            r"\textbf{Controls} &  &  &  & " + LB,
            INDENT + r"Labor scaling &  & \checkmark &  & \checkmark" + LB,
            INDENT + r"Equity offer control &  &  & \checkmark & \checkmark" + LB,
        ]
    )
    return tabular_star(colspec, lines)


def build_pair_fe_horse_race_table(df: pd.DataFrame) -> str:
    spec_order = ["baseline", "growth_endog", "equity", "growth_endog_equity"]
    spec_titles = ["Baseline", "Firm growth", "Equity offer", "Both"]
    core_labels = {
        "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
        "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    }
    control_labels = {
        "var17_e": r"$ \text{Firm growth} \times \mathds{1}(\text{Post}) $",
        "var18_e": r"$ \text{Firm growth} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
        "var19": r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) $",
        "var20": r"$ \text{Offers equity} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    }
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * len(spec_order) + "@{}"
    lines = [
        rf" & \multicolumn{{{len(spec_order)}}}{{c}}{{Contribution Rank}}" + LB,
        rf"\cmidrule(lr){{2-{len(spec_order) + 1}}}",
        " & " + " & ".join(f"({i})" for i in range(1, len(spec_order) + 1)) + LB,
        " & " + " & ".join(spec_titles) + LB,
        MID,
        rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}}" + LB,
        r"\addlinespace[2pt]",
    ]
    for param in ["var3", "var5"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textit{{Added controls}}}}" + LB,
        ]
    )
    for param in ["var17_e", "var18_e", "var19", "var20"]:
        cells = [coef_cell(_row(df, model_type="OLS", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + control_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="OLS", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            MID,
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}}" + LB,
            r"\addlinespace[2pt]",
        ]
    )
    for param in ["var3", "var5"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + core_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            r"\addlinespace[2pt]",
            rf"\multicolumn{{{len(spec_order) + 1}}}{{@{{}}l}}{{\textit{{Added controls}}}}" + LB,
        ]
    )
    for param in ["var17_e", "var18_e", "var19", "var20"]:
        cells = [coef_cell(_row(df, model_type="IV", spec=spec, param=param)) for spec in spec_order]
        lines.append(INDENT + control_labels[param] + " & " + " & ".join(cells) + LB)

    lines.extend(
        [
            MID,
            "N & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "nobs") for spec in spec_order) + LB,
            r"KP\,rk Wald F & " + " & ".join(stat_cell(_row(df, model_type="IV", spec=spec, param="var5"), "rkf", "{:.2f}") for spec in spec_order) + LB,
            MID,
            r"\textbf{Fixed Effects} &  &  &  & " + LB,
            INDENT + r"Firm $\times$ individual & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            INDENT + r"Half-year & $\checkmark$ & $\checkmark$ & $\checkmark$ & $\checkmark$" + LB,
            MID,
            r"\textbf{Controls} &  &  &  & " + LB,
            INDENT + r"Firm growth &  & \checkmark &  & \checkmark" + LB,
            INDENT + r"Equity offer control &  &  & \checkmark & \checkmark" + LB,
        ]
    )
    return tabular_star(colspec, lines)


def _share_replace_summary(df: pd.DataFrame) -> str:
    iv_row = _row(df, model_type="IV", sample_mode="all", spec_variant="share_post_mean", outcome="total_contributions_q100", param="var3_eq_shp_post")
    ols_row = _row(df, model_type="OLS", sample_mode="all", spec_variant="share_post_mean", outcome="total_contributions_q100", param="var3_eq_shp_post")
    if iv_row is None or ols_row is None:
        return "A share-based replacement specification is unavailable in the current outputs."
    iv_kp = iv_row.get("rkf")
    iv_kp_text = "--" if iv_kp is None or pd.isna(iv_kp) else f"{float(iv_kp):.2f}"
    return (
        "The share-based replacement specification is weak and noisy in the refreshed data: "
        f"the OLS interaction is {fmt_coef(float(ols_row['coef']))} "
        f"(p = {float(ols_row['pval']):.3f}), "
        f"while the IV interaction is {fmt_coef(float(iv_row['coef']))} with a KP rk Wald F of {iv_kp_text}."
    )


def _pair_battery_summary(df: pd.DataFrame) -> str:
    base = _row(df, model_type="IV", sample_mode="all", spec_variant="baseline", outcome="total_contributions_q100", param="var5")
    k_any = _row(df, model_type="IV", sample_mode="all", spec_variant="k_any_post", outcome="total_contributions_q100", param="var5")
    r_any = _row(df, model_type="IV", sample_mode="all", spec_variant="r_any_ever", outcome="total_contributions_q100", param="var5")
    if base is None or k_any is None or r_any is None:
        return "A separate pair-FE battery was run, but the winner rows were not found in the current CSV."
    return (
        "In the broader pair-FE battery, the clearest user-side attenuators are still simple binary exposure measures rather than share/count variants: "
        f"baseline IV var5 is {fmt_coef(float(base['coef']))}, "
        rf"\texttt{{k\_any\_post}} lowers it to {fmt_coef(float(k_any['coef']))}, "
        rf"and \texttt{{r\_any\_ever}} lowers it to {fmt_coef(float(r_any['coef']))}."
    )


def _restricted_summary(df: pd.DataFrame, top_df: pd.DataFrame) -> str:
    base = _row(df, model_type="IV", sample_mode="all", spec_variant="baseline", outcome="total_contributions_q100", param="var5")
    restr = _row(df, model_type="IV", sample_mode="all", spec_variant="restr_share_post", outcome="total_contributions_q100", param="var5")
    restr_pub = _row(df, model_type="IV", sample_mode="all", spec_variant="restr_share_post_public", outcome="total_contributions_q100", param="var5")
    no_top5 = _row(df, model_type="IV", sample_mode="no_top5", spec_variant="restr_share_post", outcome="total_contributions_q100", param="var5")
    support_total = float(top_df["support_obs"].sum())
    support_top5 = float(top_df.head(5)["support_obs"].sum()) if not top_df.empty else float("nan")
    top5_pct = (support_top5 / support_total) if support_total > 0 else float("nan")
    if base is None or restr is None or restr_pub is None or no_top5 is None:
        return "Restricted-stock robustness checks were run, but the key rows were not found in the current CSV."
    return (
        "Restricted-stock variants initially attenuate more, but they are not robust: "
        rf"\texttt{{restr\_share\_post}} moves IV var5 from {fmt_coef(float(base['coef']))} to {fmt_coef(float(restr['coef']))}, "
        f"adding public-post controls moves it back to {fmt_coef(float(restr_pub['coef']))}, "
        f"and dropping the top 5 support firms leaves the sample-specific IV var5 at {fmt_coef(float(no_top5['coef']))}. "
        f"The top 5 restricted-support firms account for {100.0 * top5_pct:.1f}\\% of restricted support in the user-panel regression universe."
    )


def _pair_horse_summary(df: pd.DataFrame) -> str:
    base = _row(df, model_type="IV", spec="baseline", param="var5")
    growth = _row(df, model_type="IV", spec="growth_endog", param="var5")
    equity = _row(df, model_type="IV", spec="equity", param="var5")
    both = _row(df, model_type="IV", spec="growth_endog_equity", param="var5")
    if base is None or growth is None or equity is None or both is None:
        return "The pair-FE horse-race results were unavailable in the current outputs."
    return (
        "In the pair-FE horse race, the same strict any-equity control attenuates modestly rather than amplifying: "
        f"IV var5 moves from {fmt_coef(float(base['coef']))} in baseline "
        f"to {fmt_coef(float(equity['coef']))} with equity alone, "
        f"to {fmt_coef(float(growth['coef']))} with firm growth alone, "
        f"and to {fmt_coef(float(both['coef']))} with both controls."
    )


def _baseline_horse_summary(df: pd.DataFrame) -> str:
    base = _row(df, model_type="IV", spec="baseline", param="var5")
    growth = _row(df, model_type="IV", spec="labor_scaling", param="var5")
    equity = _row(df, model_type="IV", spec="equity_comp", param="var5")
    both = _row(df, model_type="IV", spec="labor_scaling_equity_comp", param="var5")
    if base is None or growth is None or equity is None or both is None:
        return "The baseline-FE horse-race results were unavailable in the current outputs."
    return (
        "In the baseline-FE horse race, both added controls attenuate once the coverage-control term is removed: "
        f"IV var5 moves from {fmt_coef(float(base['coef']))} in baseline "
        f"to {fmt_coef(float(equity['coef']))} with equity alone, "
        f"to {fmt_coef(float(growth['coef']))} with labor scaling alone, "
        f"and to {fmt_coef(float(both['coef']))} with both controls."
    )


def build_note_tex() -> str:
    return rf"""\documentclass{{article}}
\usepackage[margin=1.0in]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{makecell}}
\usepackage{{float}}
\usepackage{{caption}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage{{dsfont}}
\usepackage[normalem]{{ulem}}
\usepackage{{setspace}}
\setstretch{{1.05}}

\newcommand{{\cleanedresultsdir}}{{../../results/cleaned/tex}}
\newcommand{{\TableInput}}[2][\linewidth]{{\input{{#2}}}}
\DeclareCaptionStyle{{noteflush}}{{%
  format=plain,
  justification=raggedright,
  singlelinecheck=false,
  font=footnotesize,
  width=\linewidth,
  skip=0pt
}}
\newcommand{{\FloatNote}}[1]{{%
  \begingroup
    \captionsetup{{style=noteflush}}%
    \caption*{{\textit{{Notes:}}~#1}}%
  \endgroup
}}

\begin{{document}}

\section*{{User Productivity: Refreshed Equity Note}}

\noindent This note reports four user-productivity empirical approaches: a data overview, a specification that replaces startup with equity under two fixed-effects designs, a baseline-FE horse race, and a pair-FE horse race.

\subsection*{{Table 1: Data overview}}
\begin{{table}}[H]
  \centering
  \caption{{User-productivity analysis universe and equity signal support}}
  \TableInput{{\cleanedresultsdir/llm_equity_user_refresh_data_overview.tex}}
  \FloatNote{{Panel A summarizes the user-productivity analysis universe. ``Firm$\times$half-year cells'' and ``Firms'' are the corresponding collapsed counts. Panel B summarizes the supporting equity signal on the same firm universe. ``Firms offering equity'' means a firm has at least one half-year with a positive equity-offer signal anywhere in the panel. Posting counts are sums over the same firm universe, using the backfill convention that firm$\times$half-year cells with no keyword-hit postings carry zero equity signal.}}
\end{{table}}

\subsection*{{Table 2: Replace startup with equity}}
\[
  \begin{{aligned}}
    y_{{ifh}} =\; & \beta_3 \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \right)
    + \beta_{{3e}} \left( \text{{Remote}}_f \times \mathds{{1}}(\text{{Post}})_h \times \text{{OffersEquity}}_f \right) \\
    & + \beta_{{eP}} \left( \text{{OffersEquity}}_f \times \mathds{{1}}(\text{{Post}})_h \right)
    + \text{{FE}} + \varepsilon_{{ifh}}.
  \end{{aligned}}
\]
\begin{{table}}[H]
  \centering
  \caption{{User productivity: replace startup with equity}}
  \TableInput{{\cleanedresultsdir/llm_equity_user_refresh_replace_startup_equity.tex}}
  \FloatNote{{Columns (1)-(2) use individual, firm, and half-year fixed effects. Columns (3)-(4) use firm$\times$individual and half-year fixed effects. The row $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})$ is the post remote effect for firms without an equity signal. The interaction row $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Offers equity}}$ is the incremental post remote effect for firms that do offer equity. The row $\text{{Offers equity}}\times\mathds{{1}}(\text{{Post}})$ is an additional post-period level shift for equity firms. Standard errors are clustered by worker and reported in parentheses; *, **, *** denote $p<0.10, 0.05, 0.01$.}}
\end{{table}}

\subsection*{{Table 3: Baseline-FE horse race}}
\begin{{table}}[H]
  \centering
  \caption{{User productivity horse race: labor scaling vs equity offers, baseline FE}}
  \TableInput{{\cleanedresultsdir/llm_equity_user_refresh_horse_race.tex}}
  \FloatNote{{Columns differ only in the added controls shown in the bottom panel. ``Labor scaling'' is the post-period median-split firm growth indicator used in the refreshed horse race. ``Equity offer control'' is the strict any-equity firm signal interacted with the post period and startup. The first two rows in each panel report the baseline remote coefficients on $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})$ and $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Startup}}$; the ``Added controls'' rows report the coefficients on the extra labor-scaling and equity-control terms themselves. The baseline and labor-scaling columns stay on their original supports, while the equity columns use the postings-covered equity sample: firms with postings but no keyword hits are coded zero, firms with keyword hits but no parse-successful LLM output are excluded, and firms with no postings coverage are excluded. Standard errors are clustered by worker; IV instruments the remote interactions with the corresponding teleworkability interactions.}}
\end{{table}}

\subsection*{{Table 4: Pair-FE horse race}}
\begin{{table}}[H]
  \centering
  \caption{{User productivity horse race: firm growth vs equity offers, pair FE}}
  \TableInput{{\cleanedresultsdir/llm_equity_user_refresh_horse_race_pairfe.tex}}
  \FloatNote{{This table uses firm$\times$individual and half-year fixed effects. ``Firm growth'' is the endogenous post-period median-split firm growth control from the pair-FE mechanism spec. ``Equity offer control'' is the strict any-equity firm signal interacted with the post period and startup. The first two rows in each panel report the baseline remote coefficients on $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})$ and $\text{{Remote}}\times\mathds{{1}}(\text{{Post}})\times\text{{Startup}}$; the ``Added controls'' rows report the coefficients on the extra growth and equity terms themselves. The baseline and growth-only columns stay on their original supports, while the equity columns use the postings-covered equity sample described above. Standard errors are clustered by worker; IV instruments the remote interactions with the corresponding teleworkability interactions.}}
\end{{table}}

\end{{document}}
"""


def main() -> None:
    ensure_dir(RESULTS_CLEANED_TEX)

    no_cb_df = pd.read_csv(require_file(NO_CB_USER_RAW, nonempty=True, purpose="user no-CB results"))
    pair_replace_df = pd.read_csv(require_file(PAIR_REPLACE_RAW, nonempty=True, purpose="user pair-FE replace-startup results"))
    horse_df = pd.read_csv(require_file(HORSE_RACE_RAW, nonempty=True, purpose="user horse-race results"))
    pair_horse_df = pd.read_csv(require_file(PAIR_HORSE_RACE_RAW, nonempty=True, purpose="user pair-FE horse-race results"))

    OUT_DATA_TEX.write_text(build_data_overview_table(), encoding="utf-8")
    OUT_REPLACE_TEX.write_text(build_replace_startup_table(no_cb_df, pair_replace_df), encoding="utf-8")
    OUT_HORSE_TEX.write_text(build_horse_race_table(horse_df), encoding="utf-8")
    OUT_PAIR_HORSE_TEX.write_text(build_pair_fe_horse_race_table(pair_horse_df), encoding="utf-8")

    note_tex = build_note_tex()
    OUT_NOTE_TEX.write_text(note_tex, encoding="utf-8")

    print(f"Wrote {OUT_DATA_TEX}")
    print(f"Wrote {OUT_REPLACE_TEX}")
    print(f"Wrote {OUT_HORSE_TEX}")
    print(f"Wrote {OUT_PAIR_HORSE_TEX}")
    print(f"Wrote {OUT_NOTE_TEX}")


if __name__ == "__main__":
    main()
