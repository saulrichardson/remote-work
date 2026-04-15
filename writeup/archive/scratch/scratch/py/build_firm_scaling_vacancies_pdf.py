#!/usr/bin/env python3
"""Render a standalone PDF with the firm scaling + vacancy tables (OLS & IV).

This bypasses reading the intermediate TeX files and injects the LaTeX
tabular code directly, avoiding any fragile `\input{...}` interactions.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from create_firm_scaling_with_vacancies_table import load_data, build_table

ROOT = Path(__file__).resolve().parents[1]
OUT_PDF = ROOT / "tex" / "firm_scaling_vacancies.pdf"


TEMPLATE = r"""\documentclass{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{dsfont}
\usepackage{booktabs}
\usepackage{makecell}
\usepackage{float}
\begin{document}

% --- OLS table ------------------------------------------------------------
\begin{table}[H]
\centering
\caption{Firm Scaling with Vacancy Outcomes — OLS}
\label{tab:firm_scaling_vacancy_ols}
{OLS_BODY}
\end{table}

\vspace{1cm}

% --- IV table -------------------------------------------------------------
\begin{table}[H]
\centering
\caption{Firm Scaling with Vacancy Outcomes — IV}
\label{tab:firm_scaling_vacancy_iv}
{IV_BODY}
\end{table}

\end{document}
"""


def main() -> None:
    df = load_data()
    ols_body = build_table(df, model="OLS")
    iv_body = build_table(df, model="IV")

    tex = TEMPLATE.replace("{OLS_BODY}", ols_body).replace("{IV_BODY}", iv_body)

    workdir = ROOT / "tex"
    workdir.mkdir(parents=True, exist_ok=True)
    tex_path = workdir / "firm_scaling_vacancies.tex"
    tex_path.write_text(tex)

    subprocess.run(["latexmk", "-pdf", tex_path.name], cwd=workdir, check=False)
    print(f"Wrote PDF to {OUT_PDF.parent / 'firm_scaling_vacancies.pdf'}")


if __name__ == "__main__":
    main()

