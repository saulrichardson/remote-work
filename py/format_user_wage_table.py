#!/usr/bin/env python3
"""Format user wage regression results into a LaTeX table and compile to PDF."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw" / "user_wage_full"
OUTPUT_DIR = PROJECT_ROOT / "results" / "cleaned"
TEX_PATH = OUTPUT_DIR / "user_wage_full_table.tex"

PARAM_LABELS = {
    "var3": r"$\text{Remote} \times \mathds{1}(\text{Post})$",
    "var5": r"$\text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup}$",
    "var4": r"$\text{Startup} \times \mathds{1}(\text{Post})$",
}


def stars(pval: float) -> str:
    if pval < 0.01:
        return r"^{***}"
    if pval < 0.05:
        return r"^{**}"
    if pval < 0.1:
        return r"^{*}"
    return ""


def fmt_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{$ {coef:.4f}{stars(pval)} $ \\ ($ {se:.4f} $)}}"


def build_table(df: pd.DataFrame) -> str:
    lines: list[str] = [
        r"\begin{tabular}{lcc}",
        r"\toprule",
        r" & OLS & IV \\",
        r"\midrule",
    ]

    for param in ["var3", "var5", "var4"]:
        label = PARAM_LABELS[param]
        ols = df[(df["model_type"] == "OLS") & (df["param"] == param)].iloc[0]
        iv = df[(df["model_type"] == "IV") & (df["param"] == param)].iloc[0]
        lines.append(
            rf"{label} & {fmt_cell(ols['coef'], ols['se'], ols['pval'])} & "
            rf"{fmt_cell(iv['coef'], iv['se'], iv['pval'])} \\"
        )

    pre_mean = df[df["model_type"] == "OLS"]["pre_mean"].iloc[0]
    nobs = int(df[df["model_type"] == "OLS"]["nobs"].iloc[0])
    rkf = df[df["model_type"] == "IV"]["rkf"].iloc[0]

    lines.extend(
        [
            r"\midrule",
            rf"Pre-COVID mean & \multicolumn{{2}}{{c}}{{{pre_mean:.2f}}} \\",
            rf"Observations & \multicolumn{{2}}{{c}}{{{nobs:,}}} \\",
            rf"Kleibergen-Paap rk Wald $F$ &  & {rkf:.2f} \\",
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    df = pd.read_csv(RAW_DIR / "consolidated_results.csv")
    df = df[df["outcome"] == "log_salary"].copy()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table_only = build_table(df)
    TEX_PATH.write_text(
        "\n".join(
            [
                r"\documentclass[11pt]{article}",
                r"\usepackage{booktabs}",
                r"\usepackage{amsmath}",
                r"\usepackage{dsfont}",
                r"\usepackage{makecell}",
                r"\usepackage[margin=1in]{geometry}",
                r"\title{User Wage Regression Results}",
                r"\author{}",
                r"\date{\today}",
                r"\begin{document}",
                r"\maketitle",
                r"\noindent\textit{Note.} The table reports OLS and IV estimates for the full user wage panel,",
                r" capturing the post-COVID remote shift and the startup interaction.",
                r"\vspace{1em}",
                r"\begin{table}[!htbp]",
                r"\centering",
                table_only,
                r"\caption{User wage regression results (full panel)}",
                r"\label{tab:user_wage_full}",
                r"\end{table}",
                r"\end{document}",
            ]
        )
    )

    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", TEX_PATH.name],
        cwd=OUTPUT_DIR,
        check=True,
    )


if __name__ == "__main__":
    main()
