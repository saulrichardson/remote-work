#!/usr/bin/env python3
import csv, os, math, argparse

def sigstars(p):
    try:
        p = float(p)
    except:
        return ''
    if p < 0.01: return '***'
    if p < 0.05: return '**'
    if p < 0.1: return '*'
    return ''

def fmt(x, nd=3):
    try:
        v = float(x)
        return f"{v:.{nd}f}"
    except:
        return x

def load_results(path):
    rows=[]
    with open(path,'r',encoding='utf-8') as f:
        r=csv.DictReader(f)
        for row in r:
            rows.append(row)
    by_out = {}
    for row in rows:
        out = row['outcome']
        by_out.setdefault(out, {}).setdefault(row['model_type'], {})[row['param']] = row
    return by_out

def build_table_for_outcome(outcome, models):
    # Robust per-outcome table: Param | OLS coef | OLS se | IV coef | IV se
    lines = []
    safe_out = outcome.replace('_','\\_')
    lines.append(f"\\subsection*{{Outcome: {safe_out} }}")
    lines.append("\\begin{tabular}{lcccc}")
    lines.append("Param & OLS coef & OLS se & IV coef & IV se \\")
    for param in ('var3','var5'):
        ols = models.get('OLS',{}).get(param)
        iv  = models.get('IV',{}).get(param)
        oc = os = ic = is_ = ''
        if ols:
            oc = fmt(ols['coef'],3) + sigstars(ols['pval'])
            os = fmt(ols['se'],3)
        if iv:
            ic = fmt(iv['coef'],3) + sigstars(iv['pval'])
            is_ = fmt(iv['se'],3)
        lines.append(f"{param} & {oc} & {os} & {ic} & {is_} \\")
    # N and pre_mean from any available (prefer OLS)
    any_row = None
    for m in ('OLS','IV'):
        if models.get(m):
            any_row = next(iter(models[m].values()))
            break
    if any_row:
        nobs = any_row.get('nobs','')
        pre = fmt(any_row.get('pre_mean',''))
        # no horizontal rules to avoid noalign issues
        lines.append(f"Pre-mean & \\multicolumn{{4}}{{c}}{{{pre}}} \\")
        lines.append(f"N & \\multicolumn{{4}}{{c}}{{{nobs}}} \\")
    lines.append("\\end{tabular}")
    lines.append("")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-tex', required=True)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.output_tex), exist_ok=True)

    by_out = load_results(args.input)
    # Order outcomes sensibly
    order = [
        'vacancies_thousands', 'filled_le_3mo', 'prop_filled_le_3mo',
        'vpe_pc_winsor',
        'hires_to_vacancies_winsor', 'avg_gap_days'
    ]
    contents = []
    contents.append("\\documentclass[11pt]{article}")
    contents.append("\\usepackage[margin=1in]{geometry}")
    contents.append("\\usepackage{setspace}")
    contents.append("\\usepackage{makecell}")
    contents.append("\\begin{document}")
    contents.append("\\section*{Vacancy Outcomes: Baseline Regressions}")
    contents.append("Spec: firm and half-year FE; SE clustered by firm. IV instruments var3 and var5 with var6,var7. Ratios use strict last-half denominators; guardrails and 1/99 winsorization.")
    contents.append("")
    for out in order:
        if out in by_out:
            contents.append(build_table_for_outcome(out, by_out[out]))
    # Minimal commentary
    # minimal commentary omitted per request for concise tables
    contents.append("\\end{document}")

    with open(args.output_tex,'w',encoding='utf-8') as fo:
        fo.write("\n".join(contents))

if __name__ == '__main__':
    main()
