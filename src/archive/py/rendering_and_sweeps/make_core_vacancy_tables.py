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

def load(path):
    by_out = {}
    with open(path,'r',encoding='utf-8') as f:
        r=csv.DictReader(f)
        for row in r:
            out=row['outcome']
            mt=row['model_type']
            pm=row['param']
            by_out.setdefault(out,{}).setdefault(mt,{})[pm]=row
    return by_out

def one_table(title, note, models):
    lines=[]
    lines.append(f"\\subsection*{{{title}}}")
    if note:
        lines.append('\\noindent\\textit{' + note + '}')
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
    # Footer
    anyrow = next(iter(models.get('OLS',{}).values()), None) or next(iter(models.get('IV',{}).values()), None)
    if anyrow:
        # Extract N and pre-mean for both columns if present
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
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-tex', required=True)
    ap.add_argument('--thresholds-base', default='', help='Base results dir containing per-threshold folders (e.g., results/raw)')
    ap.add_argument('--thresholds', nargs='*', type=int, default=[], help='Threshold days to append (e.g., 30 60 90 120 150)')
    args=ap.parse_args()

    os.makedirs(os.path.dirname(args.output_tex), exist_ok=True)
    by_out = load(args.input)

    # Three core outcomes (match original styling/titles)
    spec = [
        ('Table 1: Vacancies (Thousands)', 'Total vacancies divided by 1,000 over the half-year period.', 'vacancies_thousands'),
        ('Table 3: Proportion of Vacancies Filled Within 3 Months', 'Percentage of vacancies filled within 90 days (filled within 3 months / total vacancies).', 'prop_filled_le_3mo'),
        ('Table 6: Hiring Efficiency (Hires to Vacancies Ratio)', 'Number of hires divided by number of vacancies. Only firms with 5+ vacancies; winsorized at 1st/99th percentile.', 'hires_to_vacancies_winsor'),
    ]

    lines=[]
    lines.append('\\documentclass[11pt]{article}')
    lines.append('\\usepackage[margin=1in]{geometry}')
    lines.append('\\usepackage{amsmath}')
    lines.append('\\usepackage{dsfont}')
    lines.append('\\begin{document}')
    lines.append('\\section*{Vacancy Outcomes: OLS and IV}')
    for title, note, key in spec:
        if key in by_out:
            lines.append(one_table(title, note, by_out[key]))

    # Optionally append threshold tables for fill rate (levels)
    if args.thresholds_base and args.thresholds:
        import csv as _csv, os as _os
        def load_results(path):
            d={}
            with open(path,'r',encoding='utf-8') as f:
                r=_csv.DictReader(f)
                for row in r:
                    d.setdefault(row['outcome'],{}).setdefault(row['model_type'],{})[row['param']]=row
            return d
        def table_for_threshold(thr, models):
            out=[]
            out.append(f"\\subsection*{{Proportion Filled Within {thr} Days}}")
            out.append('\\noindent\\textit{Percentage of vacancies filled within the threshold window (filled / total vacancies).}')
            out.append('')
            out.append('\\begin{tabular}{lcc}')
            out.append('\\hline')
            out.append('\\hline')
            out.append(' & (1) & (2) \\\\')
            out.append('Parameter & OLS & IV \\\\')
            out.append('\\hline')
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
                out.append(f'{nm} & {oc} & {ic} \\\\')
                out.append(f' & {os_} & {is_} \\\\')
                if add_space:
                    out.append('[0.5em]')
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
                out.append('\\hline')
                out.append(f'N & {nobs_ols} & {nobs_iv} \\\\')
                out.append(f'Pre-mean & {pre_ols} & {pre_iv} \\\\')
                out.append(f'KP rk Wald F &  & {fmt(rkf)} \\\\')
            out.append('\\hline')
            out.append('\\hline')
            out.append('\\end{tabular}')
            out.append('\\vspace{0.5cm}')
            return "\n".join(out)
        lines.append('\\section*{Fill Rate Sensitivity by Threshold}')
        for thr in args.thresholds:
            path = os.path.join(args.thresholds_base, f'firm_scaling_vacancy_outcomes_t{thr}', 'consolidated_results.csv')
            by_out_thr = load_results(path)
            # Level table
            if 'prop_filled_le_3mo' in by_out_thr:
                lines.append(table_for_threshold(thr, by_out_thr['prop_filled_le_3mo']))
            # Percentile table for the same threshold (immediately after)
            if 'prop_filled_le_3mo_q100' in by_out_thr:
                lines.append(table_for_threshold(thr, by_out_thr['prop_filled_le_3mo_q100']))

        # Percentile outcomes section
        lines.append('\\section*{Percentile Outcomes: OLS and IV}')
        spec_q = [
            ('Vacancies (Percentile)', 'Percentile rank [1–100] within half-year.', 'vacancies_q100'),
            ('Fill Rate (Percentile)', 'Percentile rank [1–100] of fill rate within half-year.', 'prop_filled_le_3mo_q100'),
            ('Hires per Vacancy (Percentile)', 'Percentile rank [1–100] of hires-to-vacancies (winsor).', 'hires_to_vacancies_winsor_q100'),
        ]
        for title, note, key in spec_q:
            if key in by_out:
                lines.append(one_table(title, note, by_out[key]))

        # (No separate percentile-threshold section — interleaved above)

    # End document
    lines.append('\\end{document}')

    with open(args.output_tex,'w',encoding='utf-8') as fo:
        fo.write('\n'.join(lines))

if __name__=='__main__':
    main()
