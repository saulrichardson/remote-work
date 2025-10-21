#!/usr/bin/env python3
"""Create a LaTeX table for grouped occupation firm-scaling regressions (OLS + IV)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
RAW_DIR = BASE / "results" / "raw" / "firm_scaling_role_growth_groups"
CLEAN_DIR = BASE / "results" / "cleaned"
OUTPUT = CLEAN_DIR / "firm_scaling_role_growth_groups.tex"

ROLES = [
    "OpsAdmin",
    "MarketingSales",
    "Finance",
    "Technical",
]

ROLE_LABELS = {
    "OpsAdmin": "Ops/Admin",
    "MarketingSales": "Marketing/Sales",
    "Finance": "Finance",
    "Technical": "Technical",
}

PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \text{Post} \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(pval: float | None) -> str:
    for cut, sym in STAR_RULES:
        if pval is not None and pval < cut:
            return sym
    return ""


def format_cell(row: pd.Series) -> str:
    coef, se, pval = row[["coef", "se", "pval"]]
    return rf"\makecell[c]{{{coef:.4f}{stars(pval)}\\({se:.4f})}}"


def load_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    consolidated = pd.read_csv(RAW_DIR / "consolidated_results.csv")
    consolidated = consolidated[consolidated["outcome"].isin([f"growth_{r}" for r in ROLES])].copy()
    consolidated["role"] = consolidated["outcome"].str.replace("growth_", "", regex=False)

    ols = consolidated[consolidated["model_type"] == "OLS"].copy()
    iv = consolidated[consolidated["model_type"] == "IV"].copy()
    return ols, iv


def coefficient_row(frame: pd.DataFrame, param: str) -> str:
    cells = [PARAM_LABEL[param]]
    for role in ROLES:
        match = frame[(frame["role"] == role) & (frame["param"] == param)]
        cells.append(format_cell(match.iloc[0]) if not match.empty else "")
    return ' & '.join(cells) + r' \\'


def stat_row(frame: pd.DataFrame, label: str, field: str, fmt: str) -> str:
    cells = [label]
    for role in ROLES:
        match = frame[(frame["role"] == role) & (frame["param"] == "var3")]
        if match.empty or pd.isna(match.iloc[0][field]):
            cells.append("")
        else:
            cells.append(fmt.format(match.iloc[0][field]))
    return ' & '.join(cells) + r' \\'


def build_table() -> str:
    ols, iv = load_results()
    if ols.empty and iv.empty:
        raise RuntimeError("No grouped-role results found. Run the Stata spec first.")

    header = ' & '.join(["", *[ROLE_LABELS[r] for r in ROLES]]) + r' \\'

    panel_a = [r"\multicolumn{5}{@{}l}{\textbf{\uline{Panel A: OLS}}} \\"]
    for param in ("var3", "var5", "var4"):
        panel_a.append(coefficient_row(ols, param))

    panel_b = [r"\multicolumn{5}{@{}l}{\textbf{\uline{Panel B: IV}}} \\"]
    for param in ("var3", "var5", "var4"):
        panel_b.append(coefficient_row(iv, param))

    stats_ols = [
        stat_row(ols, "Pre-period mean", "pre_mean", "{:.4f}"),
        stat_row(ols, "N (OLS)", "nobs", "{:,}"),
    ]

    stats_iv: list[str] = []
    stats_iv.append(stat_row(iv, "KP rk Wald $F$", "rkf", "{:.2f}"))
    stats_iv.append(stat_row(iv, "N (IV)", "nobs", "{:,}"))

    fe_header = r"\textbf{Fixed Effects} & " + ' & '.join(["" for _ in ROLES]) + r' \\'
    fe_row = ' & '.join([r"\hspace{1em}Firm FE", *[r"$\checkmark$" for _ in ROLES]]) + r' \\'
    time_row = ' & '.join([r"\hspace{1em}Half-year FE", *[r"$\checkmark$" for _ in ROLES]]) + r' \\'

    table_lines = [
        r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lcccc}",
        r"\toprule",
        header,
        r"\midrule",
        *panel_a,
        r"\midrule",
        *stats_ols,
        r"\midrule",
        *panel_b,
        r"\midrule",
        *stats_iv,
        r"\midrule",
        fe_header,
        fe_row,
        time_row,
        r"\bottomrule",
        r"\end{tabular*}",
    ]

    tabular_block = '\n'.join(table_lines)

    return dedent(
        rf"""
          {{\centering
          \centering
          {tabular_block}
          }}
        """
    ).strip() + '\n'


def main() -> None:
    table_tex = build_table()
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(table_tex)
    print(f"Wrote grouped role LaTeX table to {OUTPUT}")


if __name__ == "__main__":
    main()
