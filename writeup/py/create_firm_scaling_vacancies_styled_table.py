#!/usr/bin/env python3
"""Styled Firm Scaling table (like firm_scaling.do), augmented with vacancies.

Outputs two TeX files to results/cleaned/ for OLS and IV with six columns:
  Growth, Growth, Join, Leave, Job Postings, Hires/Vacancies
"""

from __future__ import annotations

from pathlib import Path
import textwrap
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW_DIR = ROOT / "results" / "raw"
CLEAN_DIR = ROOT / "results" / "cleaned"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# (outcome, tag, displayed header)
COL_CONFIG: list[tuple[str, str, str]] = [
    ("growth_rate_we", "init", "Growth"),
    ("growth_rate_we", "fyh",  "Growth"),
    ("join_rate_we",   "fyh",  "Join"),
    ("leave_rate_we",  "fyh",  "Leave"),
    ("vacancies_thousands", "vac", "Job Postings (1,000s)"),
    ("hires_to_vacancies_winsor95_min3", "vac", "Hires/Job Postings"),
]

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""

def column_format(n_numeric: int) -> str:
    pad = r"@{\hspace{4pt}}"
    body = (pad + r">{\centering\arraybackslash}X" + pad) * n_numeric
    return "l" + body

PREAMBLE_FLEX = "\\centering\n"
POSTAMBLE_FLEX = ""

def build_panel_rows(
    df: pd.DataFrame,
    model: str,
    include_kp: bool,
    *,
    include_pre_mean: bool = True,
) -> tuple[str, str, str]:
    """Return (coef_block, fe_block, stats_block) strings for a given model."""
    # headers reference
    col_tags = [t for _, t, _ in COL_CONFIG]

    # Coefficient rows (with SE in makecell)
    coef_rows: list[str] = []
    INDENT = r"\hspace{1em}"
    for param in PARAM_ORDER:
        cells = [INDENT + PARAM_LABEL[param]]
        for outcome, tag, _ in COL_CONFIG:
            sub = df.query("model_type == @model and outcome == @outcome and fe_tag == @tag and param == @param")
            if sub.empty:
                cells.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                cells.append(rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}")
        coef_rows.append(" & ".join(cells) + r" \\ ")
    coef_block = "\n".join(coef_rows)

    # FE checkmarks
    INDENT = r"\hspace{1em}"
    INDENT = r"\hspace{1em}"
    INDENT = r"\hspace{1em}"
    def ind_row(label: str, mapping: dict[str, bool]) -> str:
        marks = [r"$\checkmark$" if mapping.get(t, False) else "" for t in col_tags]
        return " & ".join([INDENT + label, *marks]) + r" \\" 

    time_fe = {"init": True, "fyh": True, "vac": True}
    firm_fe = {"init": True, "fyh": True, "vac": True}
    fe_block = "\n".join([ind_row("Time FE", time_fe), ind_row("Firm FE", firm_fe)])

    # Stats rows
    def stat_row(label: str, field: str, fmt: str | None) -> str:
        vals = []
        for outcome, tag, _ in COL_CONFIG:
            sub = df[(df["model_type"] == model) & (df["outcome"] == outcome) & (df["fe_tag"] == tag)].head(1)
            if sub.empty or pd.isna(sub.iloc[0].get(field, None)):
                vals.append("")
            else:
                v = sub.iloc[0][field]
                vals.append(fmt.format(v) if fmt else str(v))
        return " & ".join([label, *vals]) + r" \\" 

    pre_mean = stat_row("Pre-Covid Mean", "pre_mean", "{:.2f}") if include_pre_mean else ""
    kp_row = stat_row("KP rk Wald F", "rkf", "{:.2f}") if include_kp else ""
    n_row = stat_row("N", "nobs", "{:,}")
    stats_lines = [line for line in [pre_mean, kp_row, n_row] if line]
    stats = "\n".join(stats_lines).strip()

    return coef_block, fe_block, stats

def build_panel(df: pd.DataFrame, model: str, include_kp: bool) -> str:
    col_tags = [t for _, t, _ in COL_CONFIG]
    header_nums = " & ".join(["", *[f"({i})" for i in range(1, len(COL_CONFIG) + 1)]]) + r" \\"  
    header_labels = " & ".join(["", *[h for _, _, h in COL_CONFIG]]) + r" \\"  

    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for outcome, tag, _ in COL_CONFIG:
            sub = df.query("model_type == @model and outcome == @outcome and fe_tag == @tag and param == @param")
            if sub.empty:
                cells.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                cells.append(rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    INDENT = r"\hspace{1em}"
    def ind_row(label: str, mapping: dict[str, bool]) -> str:
        marks = [r"$\checkmark$" if mapping.get(t, False) else "" for t in col_tags]
        return " & ".join([INDENT + label, *marks]) + r" \\" 

    time_fe = {"init": True, "fyh": True, "vac": True}
    firm_fe = {"init": True, "fyh": True, "vac": True}
    ind_block = "\n".join([ind_row("Time", time_fe), ind_row("Firm", firm_fe)])

    def stat_row(label: str, field: str, fmt: str | None) -> str:
        vals = []
        for outcome, tag, _ in COL_CONFIG:
            sub = df[(df["model_type"] == model) & (df["outcome"] == outcome) & (df["fe_tag"] == tag)].head(1)
            if sub.empty or pd.isna(sub.iloc[0].get(field, None)):
                vals.append("")
            else:
                v = sub.iloc[0][field]
                vals.append(fmt.format(v) if fmt else str(v))
        return " & ".join([label, *vals]) + r" \\" 

    pre_mean = stat_row("Pre-Covid Mean", "pre_mean", "{:.2f}")
    kp_row = stat_row("KP rk Wald F", "rkf", "{:.2f}") if include_kp else ""
    n_row = stat_row("N", "nobs", "{:,}")

    col_fmt = column_format(len(COL_CONFIG))
    tabular = textwrap.dedent(rf"""
    \centering
    \begin{{tabularx}}{{\linewidth}}{{{col_fmt}}}
    \toprule
    {header_nums}
    \midrule
    {header_labels}
    \midrule
    {coef_block}
    \midrule
    {ind_block}
    \midrule
    {pre_mean}
    {kp_row}
    {n_row}
    \bottomrule
    \end{{tabularx}}
    
    """).strip()

    return tabular

def load_data() -> pd.DataFrame:
    init = pd.read_csv(RAW_DIR / "firm_scaling_initial" / "consolidated_results.csv")
    init["fe_tag"] = "init"
    base = pd.read_csv(RAW_DIR / "firm_scaling" / "consolidated_results.csv")
    base["fe_tag"] = "fyh"
    vac = pd.read_csv(RAW_DIR / "firm_scaling_vacancy_outcomes_htv2_95" / "consolidated_results.csv")
    vac["fe_tag"] = "vac"
    return pd.concat([init, base, vac], ignore_index=True, sort=False)

def main() -> None:
    df = load_data()
    ols = build_panel(df, model="OLS", include_kp=False)
    iv  = build_panel(df, model="IV", include_kp=True)
    # Combined table (single caption with Panel A/B like productivity table)
    header_nums = " & ".join(["", *[f"({i})" for i in range(1, len(COL_CONFIG) + 1)]]) + r" \\"  
    header_labels = " & ".join(["", *[h for _, _, h in COL_CONFIG]]) + r" \\"  
    col_fmt = column_format(len(COL_CONFIG))
    coef_ols, fe_ols, stats_ols = build_panel_rows(df, model="OLS", include_kp=False, include_pre_mean=True)
    coef_iv,  fe_iv,  stats_iv  = build_panel_rows(df, model="IV",  include_kp=True,  include_pre_mean=False)
    totcols = len(COL_CONFIG) + 1
    combined = textwrap.dedent(rf"""
    \centering
    \begin{{tabularx}}{{\linewidth}}{{{col_fmt}}}
    \toprule
    {header_nums}
    \midrule
    {header_labels}
    \midrule
    \multicolumn{{{totcols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\
    {coef_ols}
    \midrule
    {stats_ols}
    \midrule
    \multicolumn{{{totcols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\
    {coef_iv}
    \midrule
    {stats_iv}
    \midrule
    \textbf{{Fixed Effects}} &  &  &  &  &  &  \\
    {fe_ols}
    \bottomrule
    \end{{tabularx}}
    
    """).strip()

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    (CLEAN_DIR / "firm_scaling_vacancies_styled_ols.tex").write_text("\n".join([
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Firm Scaling — OLS}",
        r"\label{tab:firm_scaling_vacancy_ols}",
        ols,
        r"\end{table}",
        ""]))

    (CLEAN_DIR / "firm_scaling_vacancies_styled_iv.tex").write_text("\n".join([
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Firm Scaling — IV}",
        r"\label{tab:firm_scaling_vacancy_iv}",
        iv,
        r"\end{table}",
        ""]))

    combined_path = CLEAN_DIR / "firm_scaling_precovid.tex"
    combined_path.write_text(combined + "\n")

    legacy_combined = CLEAN_DIR / "firm_scaling_vacancies_styled_combined.tex"
    if legacy_combined.exists():
        legacy_combined.unlink()

    for stale in [
        CLEAN_DIR / "firm_scaling_precovid_panel.tex",
        CLEAN_DIR / "firm_scaling_precovid_double_panel.tex",
    ]:
        if stale.exists():
            stale.unlink()

    print("Wrote:")
    print(" -", CLEAN_DIR / "firm_scaling_vacancies_styled_ols.tex")
    print(" -", CLEAN_DIR / "firm_scaling_vacancies_styled_iv.tex")
    print(" -", combined_path)

if __name__ == "__main__":
    main()
