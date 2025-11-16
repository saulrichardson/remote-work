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

OUTCOME_COLS_LEVEL = [
    ("hires_to_vacancies_winsor", "Hires per Vacancy"),
]
OUTCOME_COLS_Q100 = [
    ("hires_to_vacancies_winsor_q100", "Hires/Vacancy (Percentile)"),
]

def stars(p):
    try:
        pv = float(p)
    except Exception:
        return ""
    if pv < 0.01: return "***"
    if pv < 0.05: return "**"
    if pv < 0.10: return "*"
    return ""

def fmt(x, nd=3):
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return ""

def load_results(path: Path) -> dict:
    data = {}
    with path.open('r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            out=row['outcome']; mt=row['model_type']; pm=row['param']
            data.setdefault(out,{}).setdefault(mt,{})[pm]=row
    return data

def cell(d, out, mt, pm):
    row = d.get(out,{}).get(mt,{}).get(pm)
    if not row: return "",""
    return fmt(row['coef'])+stars(row['pval']), f"({fmt(row['se'])})"

def footer(d, out, mt):
    rows = d.get(out,{}).get(mt,{})
    if not rows: return "","",""
    anyrow = next(iter(rows.values()))
    return anyrow.get('nobs',''), fmt(anyrow.get('pre_mean','')), fmt(anyrow.get('rkf','')) if mt=='IV' else ''

def build_table(d, cols, title):
    lines=[]
    lines.append('\\begin{table}[H]')
    lines.append('\\centering')
    lines.append(f'\\caption{{{title}}}')
    colspec = 'l' + 'c'*len(cols)
    lines.append(f'\\begin{{tabular}}{{{colspec}}}')
    lines.append('\\toprule')
    lines.append(' & ' + ' & '.join(col for _,col in cols) + ' \\\\ ')
    lines.append('\\midrule')
    def panel(mt, ptitle):
        lines.append(f'\\multicolumn{{{1+len(cols)}}}{{l}}{{\\textbf{{{ptitle}}}}} \\\\ ')
        for i,(pm,label) in enumerate(PARAM_TITLES.items()):
            coefs=[]; ses=[]
            for out,_ in cols:
                c,s = cell(d,out,mt,pm)
                coefs.append(c); ses.append(s)
            lines.append(f'{label} & ' + ' & '.join(coefs) + ' \\\\ ')
            lines.append(' & ' + ' & '.join(ses) + ' \\\\ ')
            if i < len(PARAM_TITLES)-1:
                lines.append('[0.5em]')
        Ns=[footer(d,out,mt)[0] for out,_ in cols]
        Pres=[footer(d,out,mt)[1] for out,_ in cols]
        Rkfs=[footer(d,out,mt)[2] for out,_ in cols]
        lines.append('\\midrule')
        lines.append('N & ' + ' & '.join(Ns) + ' \\\\ ')
        lines.append('Pre-mean & ' + ' & '.join(Pres) + ' \\\\ ')
        if mt=='IV':
            lines.append('KP rk Wald F & ' + ' & '.join(Rkfs) + ' \\\\ ')
    panel('OLS','Panel A: OLS')
    lines.append('\\midrule')
    panel('IV','Panel B: IV')
    lines.append('\\bottomrule')
    lines.append('\\end{tabular}')
    lines.append('\\end{table}')
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--minvacs', nargs='+', type=int, required=True)
    ap.add_argument('--base', type=Path, default=RESULTS_RAW)
    ap.add_argument(
        '--output-tex',
        type=Path,
        default=RESULTS_CLEANED_TEX / 'vacancy_workflow' / 'minvac_sweep_combined.tex',
    )
    args=ap.parse_args()

    args.output_tex.parent.mkdir(parents=True, exist_ok=True)
    sections=[]
    for mv in args.minvacs:
        csvp = args.base / f'firm_scaling_vacancy_outcomes_minvac_{mv}' / 'consolidated_results.csv'
        d = load_results(csvp)
        sections.append(build_table(d, OUTCOME_COLS_LEVEL, f'Min Vacancies = {mv} (Levels)'))
        sections.append(build_table(d, OUTCOME_COLS_Q100, f'Min Vacancies = {mv} (Percentiles)'))
    doc = []
    doc.append('\\documentclass[11pt]{article}')
    doc.append('\\usepackage[margin=1in]{geometry}')
    doc.append('\\usepackage{booktabs}')
    doc.append('\\usepackage{float}')
    doc.append('\\usepackage{amsmath}')
    doc.append('\\usepackage{dsfont}')
    doc.append('\\begin{document}')
    doc.append('\\section*{Min-Vacancies Guardrail Sweep: Combined Tables}')
    doc.extend(sections)
    doc.append('\\end{document}')
    args.output_tex.write_text('\n'.join(doc), encoding='utf-8')
    print('Wrote:', args.output_tex)

if __name__=='__main__':
    main()
