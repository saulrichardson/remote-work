#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import csv


PARAM_TITLES = {
    "var3": "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $",
    "var5": "$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $",
    "var4": "$ \\mathds{1}(\\text{Post}) \\times \\text{Startup} $",
}

# Slimmed to only the threshold-sensitive outcome (Fill Rate)
OUTCOME_COLS_LEVEL = [
    ("prop_filled_le_3mo", "Fill Rate ($\\leq$ 90 days)"),
]

OUTCOME_COLS_Q100 = [
    ("prop_filled_le_3mo_q100", "Fill Rate (Percentile)"),
]


def stars(p: str | float | None) -> str:
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


def fmt(x: str | float | None, nd: int = 3) -> str:
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return ""


def load_results(path: Path) -> dict:
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


def build_combined_table(data: dict, cols: list[tuple[str,str]], title: str) -> str:
    lines: list[str] = []
    lines.append("\\begin{table}[H]")
    lines.append("\\centering")
    lines.append(f"\\caption{{{title}}}")
    colspec = 'l' + 'c'*len(cols)
    lines.append(f"\\begin{{tabular}}{{{colspec}}}")
    lines.append("\\toprule")
    lines.append(" & " + " & ".join(col for _, col in cols) + " \\\\ ")
    lines.append("\\midrule")

    def panel(model_type: str, ptitle: str):
        span = 1 + len(cols)
        lines.append(f"\\multicolumn{{{span}}}{{l}}{{\\textbf{{{ptitle}}}}} \\\\ ")
        for i, (pm, label) in enumerate(PARAM_TITLES.items()):
            coefs = []; ses = []
            for outcome, _ in cols:
                c, s = cell(data, outcome, model_type, pm)
                coefs.append(c); ses.append(s)
            lines.append(f"{label} & " + " & ".join(coefs) + " \\\\ ")
            lines.append(" & " + " & ".join(ses) + " \\\\ ")
            if i < len(PARAM_TITLES) - 1:
                lines.append('[0.5em]')
        Ns  = [footer_vals(data, o, model_type)[0] for o,_ in cols]
        Pres= [footer_vals(data, o, model_type)[1] for o,_ in cols]
        rkfs= [footer_vals(data, o, model_type)[2] for o,_ in cols]
        lines.append("\\midrule")
        lines.append("N & " + " & ".join(Ns) + " \\\\ ")
        lines.append("Pre-mean & " + " & ".join(Pres) + " \\\\ ")
        if model_type == 'IV':
            lines.append("KP rk Wald F & " + " & ".join(rkfs) + " \\\\ ")

    panel('OLS', 'Panel A: OLS')
    lines.append('\\midrule')
    panel('IV',  'Panel B: IV')
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--thresholds', nargs='+', type=int, required=True)
    ap.add_argument('--base', type=Path, default=Path('results/raw'))
    ap.add_argument('--output-tex', type=Path, default=Path('results/cleaned/vacancy_workflow/threshold_sweep_combined.tex'))
    args = ap.parse_args()

    args.output_tex.parent.mkdir(parents=True, exist_ok=True)
    sections: list[str] = []
    for t in args.thresholds:
        csv_path = args.base / f'firm_scaling_vacancy_outcomes_t{t}' / 'consolidated_results.csv'
        data = load_results(csv_path)
        title_lvl = f'Fill Rate: Threshold = {t} days (Levels)'
        title_q   = f'Fill Rate: Threshold = {t} days (Percentiles)'
        cols_level = [("prop_filled_le_3mo", f"Fill Rate ($\\leq$ {t} days)")]
        cols_q100  = [("prop_filled_le_3mo_q100", "Fill Rate (Percentile)")]
        sections.append(build_combined_table(data, cols_level, title_lvl))
        sections.append(build_combined_table(data, cols_q100, title_q))

    doc = []
    doc.append('\\documentclass[11pt]{article}')
    doc.append('\\usepackage[margin=1in]{geometry}')
    doc.append('\\usepackage{booktabs}')
    doc.append('\\usepackage{float}')
    doc.append('\\usepackage{amsmath}')
    doc.append('\\usepackage{dsfont}')
    doc.append('\\begin{document}')
    doc.append('\\section*{Threshold Sweep: Combined Tables}')
    doc.extend(sections)
    doc.append('\\end{document}')
    args.output_tex.write_text("\n".join(doc), encoding='utf-8')
    print('Wrote:', args.output_tex)


if __name__ == '__main__':
    main()
