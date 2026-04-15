#!/usr/bin/env python3
"""
Create a concise Shares vs Growth summary PDF comparing:
 - Scaling (roles, seniority): outcome as growth vs share
 - Productivity (roles, seniority): controls using change vs share

Outputs LaTeX at writeup/shares_vs_growth_summary.tex
"""
from pathlib import Path
import pandas as pd

# Minimal LaTeX escaper for table cell contents
LATEX_ESCAPES = {
    "\\": r"\\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

def escape_latex(text: str) -> str:
    if text is None:
        return ""
    s = str(text)
    for k, v in LATEX_ESCAPES.items():
        s = s.replace(k, v)
    return s

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
WRITEUP = ROOT / "writeup"

def fmt_coef(coef, se):
    if pd.isna(coef) or pd.isna(se):
        return "-"
    t = abs(coef / se) if se not in (0, None) else 0
    stars = "***" if t > 2.576 else "**" if t > 1.96 else "*" if t > 1.645 else ""
    return f"{coef:.2f}{stars}\n({se:.2f})"

def extract_table(df, group_col):
    # Expect df has columns: group_col, model_type, param, coef, se, nobs, rkf
    items = sorted(df[group_col].unique())
    rows = []
    for item in items:
        sub = df[df[group_col] == item]
        # OLS var3/var5
        r = {
            'item': item,
            'OLS var3': '-', 'OLS var5': '-',
            'IV var3': '-', 'IV var5': '-',
        }
        ols = sub[sub['model_type'] == 'OLS']
        iv = sub[sub['model_type'] == 'IV']
        for param in ('var3', 'var5'):
            row_ols = ols[ols['param'] == param]
            if not row_ols.empty:
                r[f'OLS {param}'] = fmt_coef(row_ols['coef'].values[0], row_ols['se'].values[0])
            row_iv = iv[iv['param'] == param]
            if not row_iv.empty:
                r[f'IV {param}'] = fmt_coef(row_iv['coef'].values[0], row_iv['se'].values[0])
        rows.append(r)
    out = pd.DataFrame(rows)
    return out

def latex_table(df, title, item_header):
    # Build simple LaTeX tabular
    cols = [item_header, 'OLS var3', 'OLS var5', 'IV var3', 'IV var5']
    df2 = df.rename(columns={'item': item_header})[cols]
    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(fr"\caption{{{title}}}")
    lines.append(r"\begin{tabular}{lcccc}")
    lines.append(r"\toprule")
    lines.append(f"{item_header} & OLS: var3 & OLS: var5 & IV: var3 & IV: var5 \\\\")
    lines.append(r"\midrule")
    for _, row in df2.iterrows():
        vals = [escape_latex(str(row[c]).replace('\n', ' ')) for c in cols]
        lines.append(" & ".join(vals) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)

def main():
    # Scaling: roles
    roles_growth = pd.read_csv(RAW / 'scaling_composition_roles' / 'role_scaling_results.csv')
    roles_share  = pd.read_csv(RAW / 'scaling_composition_roles' / 'role_scaling_share_results.csv')
    tab_roles_g = extract_table(roles_growth, 'role')
    tab_roles_s = extract_table(roles_share,  'role')

    # Scaling: seniority
    sen_growth = pd.read_csv(RAW / 'scaling_composition_seniority' / 'seniority_scaling_results.csv')
    sen_share  = pd.read_csv(RAW / 'scaling_composition_seniority' / 'seniority_scaling_share_results.csv')
    tab_sen_g = extract_table(sen_growth, 'seniority')
    tab_sen_s = extract_table(sen_share,  'seniority')

    # Productivity: roles (controls)
    prod_roles_g = pd.read_csv(RAW / 'user_productivity_composition' / 'role_composition_results.csv')
    prod_roles_s = pd.read_csv(RAW / 'user_productivity_composition' / 'role_composition_share_results.csv')
    tab_prod_roles_g = extract_table(prod_roles_g, 'role')
    tab_prod_roles_s = extract_table(prod_roles_s, 'role')

    # Productivity: seniority (controls)
    prod_sen_g = pd.read_csv(RAW / 'user_productivity_composition' / 'seniority_composition_results.csv')
    prod_sen_s = pd.read_csv(RAW / 'user_productivity_composition' / 'seniority_composition_share_results.csv')
    tab_prod_sen_g = extract_table(prod_sen_g, 'seniority')
    tab_prod_sen_s = extract_table(prod_sen_s, 'seniority')

    # Assemble LaTeX document
    doc = r"""\documentclass[11pt]{article}
\usepackage{booktabs}
\usepackage[margin=1in]{geometry}
\usepackage{float}
\title{Shares vs Growth Summary}
\date{\today}
\begin{document}
\maketitle
"""

    doc += "\n\section{Scaling: Roles (Outcome)}\n\n" + latex_table(tab_roles_g, "Growth Outcomes (Roles)", "Role")
    doc += "\n\n" + latex_table(tab_roles_s, "Share Outcomes (Roles)", "Role")

    doc += "\n\section{Scaling: Seniority (Outcome)}\n\n" + latex_table(tab_sen_g, "Growth Outcomes (Seniority)", "Seniority")
    doc += "\n\n" + latex_table(tab_sen_s, "Share Outcomes (Seniority)", "Seniority")

    doc += "\n\section{Productivity: Role Controls}\n\n" + latex_table(tab_prod_roles_g, "Change-in-Share Controls (Roles)", "Role")
    doc += "\n\n" + latex_table(tab_prod_roles_s, "Share-Level Controls (Roles)", "Role")

    doc += "\n\section{Productivity: Seniority Controls}\n\n" + latex_table(tab_prod_sen_g, "Change-in-Share Controls (Seniority)", "Seniority")
    doc += "\n\n" + latex_table(tab_prod_sen_s, "Share-Level Controls (Seniority)", "Seniority")

    doc += "\n\end{document}\n"

    WRITEUP.mkdir(exist_ok=True)
    out = WRITEUP / 'shares_vs_growth_summary.tex'
    out.write_text(doc)
    print(f"LaTeX written: {out}")

if __name__ == '__main__':
    main()
