#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import csv

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

PARAM_TITLES = {
    "var3": "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $",
    "var5": "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $",
    "var4": "$ \\mathds{1}(\\text{Post}) \\times \\text{Startup} $",
}

OUTCOME_COLUMNS = [
    ("emp_per_cbsa", "Employees per CBSA"),
    ("n_cbsa_headcount", "\\# CBSAs"),
    ("log_n_cbsa", "$ \\log(1 + \\#\\,\\text{CBSAs}) $"),
]


def stars(p):
    try:
        pv = float(p) if p is not None else None
    except Exception:
        return ""
    if pv is None:
        return ""
    if pv < 0.01:
        return "***"
    if pv < 0.05:
        return "**"
    if pv < 0.10:
        return "*"
    return ""


def fmt(x, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return ""


def load(path: Path) -> dict:
    data: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    with path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            out = row["outcome"]
            mt = row["model_type"]
            pm = row["param"]
            data.setdefault(out, {}).setdefault(mt, {})[pm] = row
    return data


def cell(data, outcome: str, model_type: str, param: str) -> tuple[str, str]:
    row = data.get(outcome, {}).get(model_type, {}).get(param)
    if not row:
        return "", ""
    coef = fmt(row.get("coef")) + stars(row.get("pval"))
    se = f"({fmt(row.get('se'))})"
    return coef, se


def footer_vals(data, outcome: str, model_type: str) -> tuple[str, str, str]:
    rowd = data.get(outcome, {}).get(model_type, {})
    if not rowd:
        return "", "", ""
    row = next(iter(rowd.values()))
    N = row.get("nobs", "")
    pre = fmt(row.get("pre_mean"))
    rkf = fmt(row.get("rkf")) if model_type == "IV" else ""
    return N, pre, rkf


def build_table(data: dict) -> str:
    lines: list[str] = []
    lines.append("\\begin{table}[H]")
    lines.append("\\centering")
    lines.append("\\caption{Geographic Breadth Outcomes — Combined (Columns: Outcomes; Rows: Interactions)}")
    lines.append("\\begin{tabular}{lccc}")
    lines.append("\\toprule")
    lines.append(" & " + " & ".join(col for _, col in OUTCOME_COLUMNS) + " \\\\ ")
    lines.append("\\midrule")

    def panel(model_type: str, title: str):
        lines.append(f"\\multicolumn{{4}}{{l}}{{\\textbf{{{title}}}}} \\\\ ")
        for i, (pm, label) in enumerate(PARAM_TITLES.items()):
            coefs = []
            ses = []
            for outcome, _ in OUTCOME_COLUMNS:
                c, s = cell(data, outcome, model_type, pm)
                coefs.append(c)
                ses.append(s)
            lines.append(f"{label} & " + " & ".join(coefs) + " \\\\ ")
            lines.append(" & " + " & ".join(ses) + " \\\\ ")
            if i < len(PARAM_TITLES) - 1:
                lines.append("[0.5em]")
        Ns = [footer_vals(data, outcome, model_type)[0] for outcome, _ in OUTCOME_COLUMNS]
        Pres = [footer_vals(data, outcome, model_type)[1] for outcome, _ in OUTCOME_COLUMNS]
        rkfs = [footer_vals(data, outcome, model_type)[2] for outcome, _ in OUTCOME_COLUMNS]
        lines.append("\\midrule")
        lines.append("N & " + " & ".join(Ns) + " \\\\ ")
        lines.append("Pre-mean & " + " & ".join(Pres) + " \\\\ ")
        if model_type == "IV":
            lines.append("KP rk Wald F & " + " & ".join(rkfs) + " \\\\ ")

    panel("OLS", "Panel A: OLS")
    lines.append("\\midrule")
    panel("IV", "Panel B: IV")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    # Notes footer explaining outcome definitions and specification
    lines.append("\\vspace{0.5em}")
    lines.append("\\begin{minipage}{0.95\\textwidth}")
    lines.append("\\footnotesize \\textit{Notes: Employees per CBSA equals total firm employees in the half-year divided by the number of distinct CBSAs with positive headcount in that half-year. \\# CBSAs counts distinct CBSAs with headcount $>$ 0; the log outcome uses $\\log(1 + \\#\\,\\text{CBSAs})$. Geographic breadth is computed from the LinkedIn panel (firm$\\times$CBSA$\\times$half-year), counting headcount $>$ 0. Regressions include firm and half-year fixed effects and cluster by firm. IV instruments $\\text{var3}, \\text{var5}$ with $\\text{var6}, \\text{var7}$ and include control $\\text{var4}$. Kleibergen–Paap rk Wald F is reported for IV. Pre-mean is the pre-COVID (covid=0) mean of the outcome.}"
                 )
    lines.append("\\end{minipage}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=RESULTS_RAW / "firm_msa_counts_headcount" / "consolidated_results.csv",
    )
    ap.add_argument(
        "--output-tex",
        type=Path,
        default=RESULTS_CLEANED_TEX / "geography_workflow" / "core_combined_table.tex",
    )
    args = ap.parse_args()

    args.output_tex.parent.mkdir(parents=True, exist_ok=True)
    data = load(args.input)
    tex = build_table(data)

    doc = []
    doc.append("\\documentclass[11pt]{article}")
    doc.append("\\usepackage[margin=1in]{geometry}")
    doc.append("\\usepackage{booktabs}")
    doc.append("\\usepackage{float}")
    doc.append("\\usepackage{amsmath}")
    doc.append("\\usepackage{dsfont}")
    doc.append("\\begin{document}")
    doc.append(tex)
    doc.append("\\end{document}")
    args.output_tex.write_text("\n".join(doc), encoding="utf-8")
    print("Wrote:", args.output_tex)


if __name__ == "__main__":
    main()
