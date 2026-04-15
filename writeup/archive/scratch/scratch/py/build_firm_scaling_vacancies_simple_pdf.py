#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
CLEAN = ROOT / "results" / "cleaned"
PDF_DIR = ROOT / "writeup" / "tex"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": "Remote x Post",
    "var5": "Remote x Post x Startup",
    "var4": "Post x Startup",
}

COLS = [
    ("growth_rate_we", "init", "Growth") ,
    ("growth_rate_we", "fyh",  "Growth"),
    ("join_rate_we",   "fyh",  "Join"),
    ("leave_rate_we",  "fyh",  "Leave"),
    ("hires_to_vacancies_winsor95_min2", "vac", "Hires/Job Postings"),
    ("vacancies_thousands", "vac", "Job Postings"),
]

def stars(p: float) -> str:
    if p < 0.01: return "***"
    if p < 0.05: return "**"
    if p < 0.10: return "*"
    return ""

def fmt_cell(coef: float, se: float, p: float) -> str:
    return f"{coef:.2f}{stars(p)} ({se:.2f})"

def load_df() -> pd.DataFrame:
    init = pd.read_csv(RAW / "firm_scaling_initial" / "consolidated_results.csv")
    init["fe_tag"] = "init"
    base = pd.read_csv(RAW / "firm_scaling" / "consolidated_results.csv")
    base["fe_tag"] = "fyh"
    vac  = pd.read_csv(RAW / "firm_scaling_vacancy_outcomes_htv2_95" / "consolidated_results.csv")
    vac["fe_tag"] = "vac"
    return pd.concat([init, base, vac], ignore_index=True, sort=False)

def build_tabular(df: pd.DataFrame, model: str) -> str:
    # header row
    headers = ["Parameter"] + [h for _,_,h in COLS]
    lines = ["\\begin{tabular}{l" + "c" * len(COLS) + "}", "\\hline", " & ".join(headers) + r" \\", "\\hline"]

    for param in PARAM_ORDER:
        row = [PARAM_LABEL[param]]
        for outcome, tag, _ in COLS:
            sub = df[(df.model_type == model) & (df.param == param) & (df.outcome == outcome) & (df.fe_tag == tag)]
            if sub.empty:
                row.append("")
            else:
                c, s, p = sub.iloc[0][["coef","se","pval"]]
                row.append(fmt_cell(float(c), float(s), float(p)))
        lines.append(" & ".join(row) + r" \\")

    # summary rows
    def pick(field: str, fmt: str) -> str:
        vals = []
        for outcome, tag, _ in COLS:
            sub = df[(df.model_type == model) & (df.outcome == outcome) & (df.fe_tag == tag)]
            if sub.empty or pd.isna(sub.iloc[0].get(field)):
                vals.append("")
            else:
                vals.append(fmt.format(sub.iloc[0][field]))
        return vals

    lines.append("\\hline")
    lines.append("Pre-Covid Mean & " + " & ".join(pick("pre_mean", "{:.2f}")) + r" \\")
    if model == "IV":
        lines.append("KP rk Wald F & " + " & ".join(pick("rkf", "{:.2f}")) + r" \\")
    lines.append("N & " + " & ".join(pick("nobs", "{:,}")) + r" \\")
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    return "\n".join(lines)

def main() -> None:
    df = load_df()
    body_ols = build_tabular(df, model="OLS")
    body_iv  = build_tabular(df, model="IV")

    # Write two standalone table files to results/cleaned (for \input)
    CLEAN.mkdir(parents=True, exist_ok=True)
    ols_tex = "\n".join([
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Firm Scaling with Vacancy Outcomes — OLS}",
        r"\label{tab:firm_scaling_vacancy_ols}",
        body_ols,
        r"\end{table}",
    ]) + "\n"
    iv_tex = "\n".join([
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Firm Scaling with Vacancy Outcomes — IV}",
        r"\label{tab:firm_scaling_vacancy_iv}",
        body_iv,
        r"\end{table}",
    ]) + "\n"

    (CLEAN / "firm_scaling_vacancies_simple_ols.tex").write_text(ols_tex)
    (CLEAN / "firm_scaling_vacancies_simple_iv.tex").write_text(iv_tex)

    print("Wrote:")
    print(" -", CLEAN / "firm_scaling_vacancies_simple_ols.tex")
    print(" -", CLEAN / "firm_scaling_vacancies_simple_iv.tex")

if __name__ == "__main__":
    main()
