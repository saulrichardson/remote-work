#!/usr/bin/env python3
import argparse, csv, os

def fmt(x, nd=3):
    try:
        return f"{float(x):.{nd}f}"
    except:
        return x

def sig(p):
    try:
        p=float(p)
    except:
        return ''
    if p<0.01: return '***'
    if p<0.05: return '**'
    if p<0.1: return '*'
    return ''

def load_results(path):
    by_out = {}
    with open(path,'r',encoding='utf-8') as f:
        r=csv.DictReader(f)
        for row in r:
            by_out.setdefault(row['outcome'],{}).setdefault(row['model_type'],{})[row['param']] = row
    return by_out

def table_for_threshold(thr, models):
    lines=[]
    lines.append(f"\\subsection*{{Proportion Filled Within {thr} Days}}")
    lines.append('\\noindent\\textit{Percentage of vacancies filled within the threshold window (filled / total vacancies).}')
    lines.append('')
    lines.append('\\begin{tabular}{lcc}')
    lines.append('\\hline')
    lines.append('\\hline')
    lines.append(' & (1) & (2) \\\\')
    lines.append('Parameter & OLS & IV \\\\')
    lines.append('\\hline')
    def row_block(pm, add_space):
        var_names = {
            'var3': '$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $',
            'var5': '$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $',
            'var4': '$ \\mathds{1}(\\text{Post}) \\times \\text{Startup} $'
        }
        nm = var_names.get(pm, pm)
        ols = models.get('OLS',{}).get(pm)
        iv  = models.get('IV',{}).get(pm)
        oc = fmt(ols['coef']) + sig(ols['pval']) if ols else ''
        ic = fmt(iv['coef'])  + sig(iv['pval'])  if iv  else ''
        os_ = f"({fmt(ols['se'])})" if ols else ''
        is_ = f"({fmt(iv['se'])})"  if iv  else ''
        lines.append(f'{nm} & {oc} & {ic} \\\\')
        lines.append(f' & {os_} & {is_} \\\\')
        if add_space:
            lines.append('[0.5em]')

    row_block('var3', True)
    row_block('var5', True)
    row_block('var4', False)
    anyrow = next(iter(models.get('OLS',{}).values()), None) or next(iter(models.get('IV',{}).values()), None)
    if anyrow:
        n_ols = models.get('OLS',{})
        n_iv  = models.get('IV',{})
        nobs_ols = next(iter(n_ols.values())).get('nobs','') if n_ols else ''
        nobs_iv  = next(iter(n_iv.values())).get('nobs','') if n_iv else ''
        pre_ols  = fmt(next(iter(n_ols.values())).get('pre_mean','')) if n_ols else ''
        pre_iv   = fmt(next(iter(n_iv.values())).get('pre_mean','')) if n_iv else ''
        rkf = next(iter(n_iv.values())).get('rkf','') if n_iv else ''
        lines.append('\\hline')
        lines.append(f'N & {nobs_ols} & {nobs_iv} \\\\')
        lines.append(f'Pre-mean & {pre_ols} & {pre_iv} \\\\')
        lines.append(f'KP rk Wald F &  & {fmt(rkf)} \\\\')
    lines.append('\\hline')
    lines.append('\\hline')
    lines.append('\\end{tabular}')
    lines.append('\\vspace{0.5cm}')
    return "\n".join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='Base results dir (e.g., results/raw)')
    ap.add_argument('--thresholds', nargs='+', type=int, required=True)
    ap.add_argument('--output-tex', required=True)
    args=ap.parse_args()

    os.makedirs(os.path.dirname(args.output_tex), exist_ok=True)

    lines=[]
    lines.append('\\documentclass[11pt]{article}')
    lines.append('\\usepackage[margin=1in]{geometry}')
    lines.append('\\usepackage{amsmath}')
    lines.append('\\usepackage{dsfont}')
    lines.append('\\begin{document}')
    lines.append('\\section*{Fill Rate Sensitivity by Threshold}')

    for thr in args.thresholds:
        path = os.path.join(args.base, f'firm_scaling_vacancy_outcomes_t{thr}', 'consolidated_results.csv')
        by_out = load_results(path)
        if 'prop_filled_le_3mo' in by_out:
            lines.append(table_for_threshold(thr, by_out['prop_filled_le_3mo']))

    lines.append('\\end{document}')

    with open(args.output_tex,'w',encoding='utf-8') as fo:
        fo.write('\n'.join(lines))

if __name__=='__main__':
    main()
