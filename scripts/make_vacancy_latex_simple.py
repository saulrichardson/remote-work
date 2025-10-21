#!/usr/bin/env python3
import argparse, csv, os as _os

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

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output-tex', required=True)
    args=ap.parse_args()

    _os.makedirs(_os.path.dirname(args.output_tex), exist_ok=True)
    by_out = load(args.input)
    order = [
        'vacancies_thousands','filled_le_3mo','prop_filled_le_3mo',
        'vpe_pc_winsor',
        'hires_to_vacancies_winsor','avg_gap_days'
    ]
    lines=[]
    lines.append('\\documentclass[11pt]{article}')
    lines.append('\\usepackage[margin=1in]{geometry}')
    lines.append('\\usepackage{amssymb}')
    lines.append('\\usepackage{amsmath}')  # For \text
    lines.append('\\usepackage{dsfont}')  # For \mathds
    lines.append('\\begin{document}')
    lines.append('\\section*{Vacancy Outcomes: OLS and IV}')
    # Better table titles
    table_titles = {
        'vacancies_thousands': 'Vacancies (Thousands)',
        'filled_le_3mo': 'Vacancies Filled Within 3 Months',
        'prop_filled_le_3mo': 'Proportion of Vacancies Filled Within 3 Months',
        'vpe_pc_winsor': 'Vacancy Rate (Per Pre-COVID Employees)',
        'hires_to_vacancies_winsor': 'Hiring Efficiency (Hires to Vacancies Ratio)',
        'avg_gap_days': 'Average Days to Fill Vacancy',
    }
    notes = {
        'vacancies_thousands': 'Total count of job vacancies divided by 1,000 in the half-year period.',
        'filled_le_3mo': 'Number of posted vacancies that were filled within 90 days of posting.',
        'prop_filled_le_3mo': 'Percentage of vacancies filled within 90 days (filled within 3 months / total vacancies).',
        'vpe_pc_winsor': 'Vacancies divided by firm employment in 2019H2 (pre‑COVID baseline). Only firms with 100+ baseline employees; winsorized at 1st/99th percentile.',
        'hires_to_vacancies_winsor': 'Number of hires divided by number of vacancies. Only firms with 5+ vacancies; winsorized at 1st/99th percentile.',
        'avg_gap_days': 'Average number of days between vacancy posting and filling. Unfilled vacancies counted as 365 days.',
    }
    for i, out in enumerate(order):
        if out not in by_out: continue
        # Use the better title if available, otherwise fall back to cleaned variable name
        title = table_titles.get(out, out.replace('_',' ').title())
        lines.append('')
        lines.append(f'\\subsection*{{Table {i+1}: {title}}}')
        if out in notes:
            lines.append('\\noindent\\textit{' + notes[out] + '}')
        lines.append('')
        lines.append('\\begin{tabular}{lcc}')
        lines.append('\\hline')
        lines.append('\\hline')
        lines.append(' & (1) & (2) \\\\')
        lines.append('Parameter & OLS & IV \\\\')
        lines.append('\\hline')
        # Map variable names to their proper LaTeX formatting
        var_names = {
            'var3': '$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $',
            'var5': '$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $',
            'var4': '$ \\mathds{1}(\\text{Post}) \\times \\text{Startup} $'
        }
        for pm in ('var3','var5','var4'):
            ols = by_out[out].get('OLS',{}).get(pm)
            iv  = by_out[out].get('IV',{}).get(pm)
            oc=os=ic=is_=''
            if ols:
                oc = fmt(ols['coef']) + sig(ols['pval'])
                os = f"({fmt(ols['se'])})"
            else:
                oc = ''
                os = ''
            if iv:
                ic = fmt(iv['coef']) + sig(iv['pval'])
                is_ = f"({fmt(iv['se'])})"
            else:
                ic = ''
                is_ = ''
            # Coefficient row (use proper name if available)
            param_name = var_names.get(pm, pm)
            lines.append(f'{param_name} & {oc} & {ic} \\\\')
            # Standard error row (indented)
            lines.append(f' & {os} & {is_} \\\\')
            # Add small vertical space between variables (except after the last one)
            if pm in ('var3', 'var5'):
                lines.append('[0.5em]')
        lines.append('\\hline')
        # footer - get statistics separately for OLS and IV
        ols_row = next(iter(by_out[out].get('OLS',{}).values()), None)
        iv_row = next(iter(by_out[out].get('IV',{}).values()), None)
        
        if ols_row or iv_row:
            # Get N for OLS and IV - always show separately
            n_ols = ols_row.get('nobs','') if ols_row else ''
            n_iv = iv_row.get('nobs','') if iv_row else ''
            
            if n_ols or n_iv:
                lines.append(f'N & {n_ols if n_ols else ""} & {n_iv if n_iv else ""} \\\\')
            
            # Get pre-mean for each - always show separately
            pre_ols = fmt(ols_row.get('pre_mean','')) if ols_row and ols_row.get('pre_mean') else ''
            pre_iv = fmt(iv_row.get('pre_mean','')) if iv_row and iv_row.get('pre_mean') else ''
            
            if pre_ols or pre_iv:
                lines.append(f'Pre-mean & {pre_ols} & {pre_iv} \\\\')
            
            # Add KP F-statistic for IV (only in IV column)
            rkf = iv_row.get('rkf','') if iv_row else ''
            if rkf:
                lines.append(f'KP rk Wald F &  & {fmt(rkf)} \\\\')
        lines.append('\\hline')
        lines.append('\\hline')
        lines.append('\\end{tabular}')
        lines.append('\\vspace{0.5cm}')
    lines.append('\\end{document}')

    with open(args.output_tex,'w',encoding='utf-8') as fo:
        fo.write('\n'.join(lines))

if __name__=='__main__':
    main()
