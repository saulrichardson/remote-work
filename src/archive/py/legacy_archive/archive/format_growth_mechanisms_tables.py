#!/usr/bin/env python3
"""
Format growth mechanisms results into LaTeX tables
"""
import pandas as pd
import numpy as np

def format_coefficient(coef, se, stars=''):
    """Format coefficient with standard error"""
    return f"{coef:.2f}{stars}"

def format_se(se):
    """Format standard error in parentheses"""
    return f"({se:.2f})"

def get_significance_stars(coef, se):
    """Calculate significance stars based on t-stat"""
    if pd.isna(coef) or pd.isna(se) or se == 0:
        return ''
    t_stat = abs(coef / se)
    if t_stat > 2.576:  # 1% level
        return '***'
    elif t_stat > 1.96:  # 5% level
        return '**'
    elif t_stat > 1.645:  # 10% level
        return '*'
    return ''

def create_first_stage_table():
    """Create first-stage regression table"""
    # Read first-stage results - note the special CSV format with = prefix
    with open('/Users/saul/Dropbox/Remote Work Startups/main/results/cleaned/growth_first_stage.csv', 'r') as f:
        lines = f.readlines()
    
    # Parse the results manually due to special format
    results = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if 'ind_growth_postavg_lo' in line:
            results['ind_coef'] = float(lines[i].split('=')[2].strip('"\n'))
            results['ind_se'] = float(lines[i+1].split('=')[2].strip('"\n'))
        elif 'msa_growth_postavg_lo' in line:
            results['msa_coef'] = float(lines[i].split('=')[2].strip('"\n'))
            results['msa_se'] = float(lines[i+1].split('=')[2].strip('"\n'))
        elif 'tile_rent' in line and '=' in line:
            results['rent_coef'] = float(lines[i].split('=')[2].strip('"\n'))
            results['rent_se'] = float(lines[i+1].split('=')[2].strip('"\n'))
        elif 'tile_hhi' in line:
            results['hhi_coef'] = float(lines[i].split('=')[2].strip('"\n'))
            results['hhi_se'] = float(lines[i+1].split('=')[2].strip('"\n'))
        elif '_cons' in line:
            results['cons_coef'] = float(lines[i].split('=')[2].strip('"\n'))
            results['cons_se'] = float(lines[i+1].split('=')[2].strip('"\n'))
        elif '="N"' in line:
            results['n_obs'] = int(float(lines[i].split('=')[2].strip('"\n')))
        elif '="r2"' in line:
            results['r2'] = float(lines[i].split('=')[2].strip('"\n'))
        i += 1
    
    table = r"""\begin{table}[H]
\centering
\caption{First-Stage Regression: Firm Growth Residualization}
\begin{tabular}{lc}
\toprule
 & Dep Var: \\
 & Firm Growth Rate \\
\midrule
Industry growth (leave-one-out) & %.3f*** \\
                               & (%.3f) \\
MSA growth (leave-one-out)     & %.3f%s \\
                               & (%.3f) \\
High rent (above median)       & %.3f*** \\
                               & (%.3f) \\
High HHI (above median)        & %.3f*** \\
                               & (%.3f) \\
Constant                       & %.3f*** \\
                               & (%.3f) \\
\midrule
Observations                   & %s \\
R-squared                      & %.3f \\
\bottomrule
\multicolumn{2}{l}{\footnotesize \textit{Notes:} Growth rate is average post-COVID employment growth.} \\
\multicolumn{2}{l}{\footnotesize *** p$<$0.01, ** p$<$0.05, * p$<$0.10} \\
\end{tabular}
\end{table}""" % (results['ind_coef'], results['ind_se'], 
                 results.get('msa_coef', 0.000), 
                 get_significance_stars(results.get('msa_coef', 0), results.get('msa_se', 1)),
                 results.get('msa_se', 0.000),
                 results['rent_coef'], results['rent_se'], 
                 results['hhi_coef'], results['hhi_se'], 
                 results['cons_coef'], results['cons_se'], 
                 f"{results['n_obs']:,}", results['r2'])
    
    return table

def create_main_results_table(fe_type="worker-firm"):
    """Create main results table"""
    # Read main results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/cleaned/growth_mechanisms_results.csv')
    
    # Filter for the relevant FE type
    if fe_type == "worker-firm":
        df_fe = df[df['spec_name'].str.contains('_wf')]
        title = "Worker-Firm Fixed Effects"
    else:
        df_fe = df[df['spec_name'].str.contains('_sep')]
        title = "Separate Fixed Effects"
    
    # Extract coefficients for each specification
    specs = ['baseline', 'endog', 'exog']
    results = {}
    
    for spec in specs:
        # OLS
        ols_row = df_fe[df_fe['spec_name'].str.contains(f'{spec}_ols')]
        if not ols_row.empty:
            results[f'{spec}_ols_var3'] = ols_row['var3_coef'].values[0]
            results[f'{spec}_ols_var3_se'] = ols_row['var3_se'].values[0]
            results[f'{spec}_ols_var5'] = ols_row['var5_coef'].values[0]
            results[f'{spec}_ols_var5_se'] = ols_row['var5_se'].values[0]
        
        # IV
        iv_row = df_fe[df_fe['spec_name'].str.contains(f'{spec}_iv')]
        if not iv_row.empty:
            results[f'{spec}_iv_var3'] = iv_row['var3_coef'].values[0]
            results[f'{spec}_iv_var3_se'] = iv_row['var3_se'].values[0]
            results[f'{spec}_iv_var5'] = iv_row['var5_coef'].values[0]
            results[f'{spec}_iv_var5_se'] = iv_row['var5_se'].values[0]
            results[f'{spec}_n'] = int(iv_row['n_obs'].values[0])
            results[f'{spec}_rkf'] = iv_row['rkf'].values[0]
    
    # Format table
    table = f"""\\begin{{table}}[H]
\\centering
\\caption{{{title}}}
\\begin{{tabular}}{{lccc}}
\\toprule
 & \\multicolumn{{3}}{{c}}{{Dep Var: Total Productivity}} \\\\
\\cmidrule{{2-4}}
 & (1) & (2) & (3) \\\\
\\midrule
\\multicolumn{{4}}{{l}}{{\\textbf{{Panel A: OLS}}}} \\\\
\\addlinespace
Remote $\\times$ Post & {format_coefficient(results['baseline_ols_var3'], results['baseline_ols_var3_se'], get_significance_stars(results['baseline_ols_var3'], results['baseline_ols_var3_se']))} & {format_coefficient(results['endog_ols_var3'], results['endog_ols_var3_se'], get_significance_stars(results['endog_ols_var3'], results['endog_ols_var3_se']))} & {format_coefficient(results['exog_ols_var3'], results['exog_ols_var3_se'], get_significance_stars(results['exog_ols_var3'], results['exog_ols_var3_se']))} \\\\
 & {format_se(results['baseline_ols_var3_se'])} & {format_se(results['endog_ols_var3_se'])} & {format_se(results['exog_ols_var3_se'])} \\\\
\\addlinespace[0.5em]
Remote $\\times$ Post $\\times$ Startup & {format_coefficient(results['baseline_ols_var5'], results['baseline_ols_var5_se'], get_significance_stars(results['baseline_ols_var5'], results['baseline_ols_var5_se']))} & {format_coefficient(results['endog_ols_var5'], results['endog_ols_var5_se'], get_significance_stars(results['endog_ols_var5'], results['endog_ols_var5_se']))} & {format_coefficient(results['exog_ols_var5'], results['exog_ols_var5_se'], get_significance_stars(results['exog_ols_var5'], results['exog_ols_var5_se']))} \\\\
 & {format_se(results['baseline_ols_var5_se'])} & {format_se(results['endog_ols_var5_se'])} & {format_se(results['exog_ols_var5_se'])} \\\\
\\midrule
N & {results['baseline_n']:,} & {results['endog_n']:,} & {results['exog_n']:,} \\\\
\\midrule
\\multicolumn{{4}}{{l}}{{\\textbf{{Panel B: IV}}}} \\\\
\\addlinespace
Remote $\\times$ Post & {format_coefficient(results['baseline_iv_var3'], results['baseline_iv_var3_se'], get_significance_stars(results['baseline_iv_var3'], results['baseline_iv_var3_se']))} & {format_coefficient(results['endog_iv_var3'], results['endog_iv_var3_se'], get_significance_stars(results['endog_iv_var3'], results['endog_iv_var3_se']))} & {format_coefficient(results['exog_iv_var3'], results['exog_iv_var3_se'], get_significance_stars(results['exog_iv_var3'], results['exog_iv_var3_se']))} \\\\
 & {format_se(results['baseline_iv_var3_se'])} & {format_se(results['endog_iv_var3_se'])} & {format_se(results['exog_iv_var3_se'])} \\\\
\\addlinespace[0.5em]
Remote $\\times$ Post $\\times$ Startup & {format_coefficient(results['baseline_iv_var5'], results['baseline_iv_var5_se'], get_significance_stars(results['baseline_iv_var5'], results['baseline_iv_var5_se']))} & {format_coefficient(results['endog_iv_var5'], results['endog_iv_var5_se'], get_significance_stars(results['endog_iv_var5'], results['endog_iv_var5_se']))} & {format_coefficient(results['exog_iv_var5'], results['exog_iv_var5_se'], get_significance_stars(results['exog_iv_var5'], results['exog_iv_var5_se']))} \\\\
 & {format_se(results['baseline_iv_var5_se'])} & {format_se(results['endog_iv_var5_se'])} & {format_se(results['exog_iv_var5_se'])} \\\\
\\midrule
N & {results['baseline_n']:,} & {results['endog_n']:,} & {results['exog_n']:,} \\\\
KP rk Wald F & {results['baseline_rkf']:.2f} & {results['endog_rkf']:.2f} & {results['exog_rkf']:.2f} \\\\
\\midrule
Endogenous growth & & \\checkmark & \\\\
Exogenous growth & & & \\checkmark \\\\
\\bottomrule
\\end{{tabular}}
\\begin{{tablenotes}}
\\small
\\item \\textit{{Notes:}} {"Worker-firm interacted fixed effects with time FE." if fe_type == "worker-firm" else "Separate user, firm, and time fixed effects."} 
Raw firm growth is the average post-COVID employment growth rate (above/below median). 
Residualized growth is predicted by industry/MSA trends, rent, and HHI.
Standard errors clustered by user in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\\end{{tablenotes}}
\\end{{table}}"""
    
    return table

def create_latex_document():
    """Create complete LaTeX document"""
    doc = r"""\documentclass[11pt]{article}
\usepackage{booktabs}
\usepackage{array}
\usepackage{multirow}
\usepackage{graphicx}
\usepackage[margin=1in]{geometry}
\usepackage{adjustbox}
\usepackage{threeparttable}
\usepackage{amssymb}
\usepackage{amsmath}
\usepackage{float}

\title{Growth Mechanisms Analysis}
\date{\today}

\begin{document}

\maketitle

\section{Growth Mechanisms Analysis}

This analysis examines how firm growth moderates the remote work productivity effect. Define:
\begin{itemize}
\item var3 = Remote$_i$ × Post$_t$
\item var4 = Post$_t$ × Startup$_i$
\item var5 = Remote$_i$ × Post$_t$ × Startup$_i$
\end{itemize}

We estimate three specifications:

\textbf{Baseline:} The standard remote work effect without growth interactions:
\begin{equation}
y_{it} = \beta_1 \text{var3}_{it} + \beta_2 \text{var4}_{it} + \beta_3 \text{var5}_{it} + \alpha_{i,j} + \delta_t + \varepsilon_{it}
\end{equation}

\textbf{Endogenous Growth:} Adds controls for high-growth firms (above median growth):
\begin{equation}
\begin{aligned}
y_{it} = &\beta_1 \text{var3}_{it} + \beta_2 \text{var4}_{it} + \beta_3 \text{var5}_{it} \\
&+ \beta_4 \text{Post}_t \times \text{HighGrowth}_j + \beta_5 \text{Post}_t \times \text{HighGrowth}_j \times \text{Startup}_i \\
&+ \alpha_{i,j} + \delta_t + \varepsilon_{it}
\end{aligned}
\end{equation}

\textbf{Exogenous Growth:} Uses growth residualized on industry/MSA trends, rent, and market concentration:
\begin{equation}
\text{Growth}_j = \pi_1 \text{IndGrowth}_{-j} + \pi_2 \text{MSAGrowth}_{-j} + \pi_3 \text{Rent}_j + \pi_4 \text{HHI}_j + \nu_j
\end{equation}
Then adds controls for high residualized growth ($\hat{\nu}_j > \text{median}$) in the same form as endogenous growth.

The analysis compares two fixed effects specifications: (1) worker-firm interacted fixed effects ($\alpha_{i,j}$) that absorb time-invariant match quality, and (2) separate worker ($\alpha_i$) and firm ($\alpha_j$) fixed effects that allow estimation of firm-level heterogeneity.

\section{First-Stage: Growth Residualization}

"""
    
    # Add first-stage table
    doc += create_first_stage_table()
    
    # Add worker-firm FE table
    doc += "\n\n\\section{Worker-Firm Fixed Effects}\n\n"
    doc += create_main_results_table("worker-firm")
    
    # Add separate FE table
    doc += "\n\n\\section{Separate Fixed Effects}\n\n"
    doc += create_main_results_table("separate")
    
    doc += "\n\n\\end{document}"
    
    return doc

if __name__ == "__main__":
    # Create LaTeX document
    latex_content = create_latex_document()
    
    # Write to file
    output_file = "/Users/saul/Dropbox/Remote Work Startups/main/writeup/growth_mechanisms_final.tex"
    with open(output_file, 'w') as f:
        f.write(latex_content)
    
    print(f"LaTeX file created: {output_file}")