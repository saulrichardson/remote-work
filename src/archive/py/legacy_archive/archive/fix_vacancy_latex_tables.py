#!/usr/bin/env python3
"""
Fix LaTeX formatting in vacancy outcome tables by converting CSV results to proper LaTeX.
"""

import pandas as pd
import numpy as np

def format_coef_se(coef, se, pval):
    """Format coefficient with SE and significance stars."""
    stars = ""
    if pval < 0.01:
        stars = "***"
    elif pval < 0.05:
        stars = "**"
    elif pval < 0.10:
        stars = "*"
    return f"{coef:.3f}{stars}", f"{se:.3f}"

def create_vacancy_latex_tables():
    """Create properly formatted LaTeX tables from CSV results."""
    
    # Read the consolidated results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/firm_scaling_vacancy_outcomes/consolidated_results.csv')
    
    # Get unique outcomes
    outcomes = df['outcome'].unique()
    
    # Start building LaTeX content
    latex_content = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\begin{document}
\section*{Vacancy Outcomes: OLS and IV}
"""
    
    for outcome in outcomes:
        # Filter data for this outcome
        outcome_df = df[df['outcome'] == outcome]
        
        # Get OLS results
        ols_df = outcome_df[outcome_df['model_type'] == 'OLS']
        ols_var3 = ols_df[ols_df['param'] == 'var3'].iloc[0] if len(ols_df[ols_df['param'] == 'var3']) > 0 else None
        ols_var5 = ols_df[ols_df['param'] == 'var5'].iloc[0] if len(ols_df[ols_df['param'] == 'var5']) > 0 else None
        
        # Get IV results  
        iv_df = outcome_df[outcome_df['model_type'] == 'IV']
        iv_var3 = iv_df[iv_df['param'] == 'var3'].iloc[0] if len(iv_df[iv_df['param'] == 'var3']) > 0 else None
        iv_var5 = iv_df[iv_df['param'] == 'var5'].iloc[0] if len(iv_df[iv_df['param'] == 'var5']) > 0 else None
        
        if ols_var3 is None or iv_var3 is None:
            continue
            
        # Format outcome name for LaTeX
        outcome_latex = outcome.replace('_', r'\_')
        
        # Build table for this outcome
        latex_content += f"""
\\subsection*{{Outcome: {outcome_latex}}}
\\begin{{tabular}}{{lrrrr}}
Param & OLS coef & OLS se & IV coef & IV se \\\\
"""
        
        # var3 row
        ols_coef3, ols_se3 = format_coef_se(ols_var3['coef'], ols_var3['se'], ols_var3['pval'])
        iv_coef3, iv_se3 = format_coef_se(iv_var3['coef'], iv_var3['se'], iv_var3['pval'])
        latex_content += f"var3 & {ols_coef3} & {ols_se3} & {iv_coef3} & {iv_se3} \\\\\n"
        
        # var5 row
        if ols_var5 is not None and iv_var5 is not None:
            ols_coef5, ols_se5 = format_coef_se(ols_var5['coef'], ols_var5['se'], ols_var5['pval'])
            iv_coef5, iv_se5 = format_coef_se(iv_var5['coef'], iv_var5['se'], iv_var5['pval'])
            latex_content += f"var5 & {ols_coef5} & {ols_se5} & {iv_coef5} & {iv_se5} \\\\\n"
        
        # Add pre-mean and N
        pre_mean = ols_var3['pre_mean']
        n_obs = int(ols_var3['nobs'])
        latex_content += f"\\multicolumn{{5}}{{l}}{{Pre-mean: {pre_mean:.3f} \\quad N: {n_obs}}} \\\\\n"
        
        latex_content += "\\end{tabular}\n"
    
    latex_content += """
\\end{document}"""
    
    # Write the fixed LaTeX file
    with open('/Users/saul/Dropbox/Remote Work Startups/main/results/cleaned/firm_scaling_vacancy_outcomes/vacancy_tables_fixed.tex', 'w') as f:
        f.write(latex_content)
    
    print("Created vacancy_tables_fixed.tex with proper LaTeX formatting")
    
    # Also create a simpler summary table
    create_summary_latex()

def create_summary_latex():
    """Create a properly formatted summary.tex file."""
    
    # Read the consolidated results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/firm_scaling_vacancy_outcomes/consolidated_results.csv')
    
    # Get unique outcomes
    outcomes = df['outcome'].unique()
    
    # Start building LaTeX content
    latex_content = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{setspace}
\usepackage{makecell}
\begin{document}
\section*{Vacancy Outcomes: Baseline Regressions}
Spec: firm and half-year FE; SE clustered by firm. IV instruments var3 and var5 with var6,var7. Ratios use strict last-half denominators; guardrails and 1/99 winsorization.

"""
    
    for outcome in outcomes:
        # Filter data for this outcome
        outcome_df = df[df['outcome'] == outcome]
        
        # Get OLS results
        ols_df = outcome_df[outcome_df['model_type'] == 'OLS']
        ols_var3 = ols_df[ols_df['param'] == 'var3'].iloc[0] if len(ols_df[ols_df['param'] == 'var3']) > 0 else None
        ols_var5 = ols_df[ols_df['param'] == 'var5'].iloc[0] if len(ols_df[ols_df['param'] == 'var5']) > 0 else None
        
        # Get IV results  
        iv_df = outcome_df[outcome_df['model_type'] == 'IV']
        iv_var3 = iv_df[iv_df['param'] == 'var3'].iloc[0] if len(iv_df[iv_df['param'] == 'var3']) > 0 else None
        iv_var5 = iv_df[iv_df['param'] == 'var5'].iloc[0] if len(iv_df[iv_df['param'] == 'var5']) > 0 else None
        
        if ols_var3 is None or iv_var3 is None:
            continue
            
        # Format outcome name for LaTeX
        outcome_latex = outcome.replace('_', r'\_')
        
        # Build table for this outcome
        latex_content += f"""\\subsection*{{Outcome: {outcome_latex} }}
\\begin{{tabular}}{{lcccc}}
Param & OLS coef & OLS se & IV coef & IV se \\\\
"""
        
        # var3 row
        ols_coef3, ols_se3 = format_coef_se(ols_var3['coef'], ols_var3['se'], ols_var3['pval'])
        iv_coef3, iv_se3 = format_coef_se(iv_var3['coef'], iv_var3['se'], iv_var3['pval'])
        latex_content += f"var3 & {ols_coef3} & {ols_se3} & {iv_coef3} & {iv_se3} \\\\\n"
        
        # var5 row
        if ols_var5 is not None and iv_var5 is not None:
            ols_coef5, ols_se5 = format_coef_se(ols_var5['coef'], ols_var5['se'], ols_var5['pval'])
            iv_coef5, iv_se5 = format_coef_se(iv_var5['coef'], iv_var5['se'], iv_var5['pval'])
            latex_content += f"var5 & {ols_coef5} & {ols_se5} & {iv_coef5} & {iv_se5} \\\\\n"
        
        # Add pre-mean and N
        pre_mean = ols_var3['pre_mean']
        n_obs = int(ols_var3['nobs'])
        latex_content += f"Pre-mean & \\multicolumn{{4}}{{c}}{{{pre_mean:.3f}}} \\\\\n"
        latex_content += f"N & \\multicolumn{{4}}{{c}}{{{n_obs}}} \\\\\n"
        
        latex_content += "\\end{tabular}\n\n"
    
    latex_content += """\\end{document}
"""
    
    # Write the fixed summary file
    with open('/Users/saul/Dropbox/Remote Work Startups/main/results/cleaned/firm_scaling_vacancy_outcomes/summary_fixed.tex', 'w') as f:
        f.write(latex_content)
    
    print("Created summary_fixed.tex with proper LaTeX formatting")

if __name__ == "__main__":
    create_vacancy_latex_tables()