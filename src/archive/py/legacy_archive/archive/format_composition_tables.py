#!/usr/bin/env python3
"""
Format composition results into LaTeX tables
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

def create_role_table():
    """Create role composition effects table"""
    # Read role results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/user_productivity_composition/role_composition_results.csv')
    
    # Get baseline results
    baseline_ols = df[(df['role'] == 'Baseline') & (df['model_type'] == 'OLS')]
    baseline_iv = df[(df['role'] == 'Baseline') & (df['model_type'] == 'IV')]
    
    # Extract baseline coefficients
    baseline_var3_ols = baseline_ols[baseline_ols['param'] == 'var3']['coef'].values[0]
    baseline_var3_ols_se = baseline_ols[baseline_ols['param'] == 'var3']['se'].values[0]
    baseline_var5_ols = baseline_ols[baseline_ols['param'] == 'var5']['coef'].values[0]
    baseline_var5_ols_se = baseline_ols[baseline_ols['param'] == 'var5']['se'].values[0]
    
    baseline_var3_iv = baseline_iv[baseline_iv['param'] == 'var3']['coef'].values[0]
    baseline_var3_iv_se = baseline_iv[baseline_iv['param'] == 'var3']['se'].values[0]
    baseline_var5_iv = baseline_iv[baseline_iv['param'] == 'var5']['coef'].values[0]
    baseline_var5_iv_se = baseline_iv[baseline_iv['param'] == 'var5']['se'].values[0]
    
    baseline_n = int(baseline_ols['nobs'].values[0])
    baseline_rkf = baseline_iv['rkf'].values[0]
    
    # Roles to process
    roles = ['Admin', 'Engineer', 'Finance', 'Marketing', 'Operations', 'Sales', 'Scientist']
    
    # Start building table
    table = r"""\begin{table}[H]
\centering
\caption{Role Composition Effects on Remote Work Productivity}
\label{tab:role_composition}
\begin{adjustbox}{width=\textwidth}
\begin{tabular}{l*{8}{c}}
\toprule
 & (1) & (2) & (3) & (4) & (5) & (6) & (7) & (8) \\
\midrule
\multicolumn{9}{l}{\textbf{Panel A: OLS}} \\
\addlinespace
"""
    
    # Panel A: OLS - Remote × Post
    table += "Remote $\\times$ Post & "
    table += f"{format_coefficient(baseline_var3_ols, baseline_var3_ols_se, get_significance_stars(baseline_var3_ols, baseline_var3_ols_se))}"
    
    for role in roles:
        role_ols = df[(df['role'] == role) & (df['model_type'] == 'OLS')]
        var3_row = role_ols[role_ols['param'] == 'var3']
        if not var3_row.empty:
            coef = var3_row['coef'].values[0]
            se = var3_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post
    table += " & " + format_se(baseline_var3_ols_se)
    for role in roles:
        role_ols = df[(df['role'] == role) & (df['model_type'] == 'OLS')]
        var3_row = role_ols[role_ols['param'] == 'var3']
        if not var3_row.empty:
            se = var3_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n\\addlinespace[0.5em]\n"
    
    # Panel A: OLS - Remote × Post × Startup
    table += "Remote $\\times$ Post $\\times$ Startup & "
    table += f"{format_coefficient(baseline_var5_ols, baseline_var5_ols_se, get_significance_stars(baseline_var5_ols, baseline_var5_ols_se))}"
    
    for role in roles:
        role_ols = df[(df['role'] == role) & (df['model_type'] == 'OLS')]
        var5_row = role_ols[role_ols['param'] == 'var5']
        if not var5_row.empty:
            coef = var5_row['coef'].values[0]
            se = var5_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post × Startup
    table += " & " + format_se(baseline_var5_ols_se)
    for role in roles:
        role_ols = df[(df['role'] == role) & (df['model_type'] == 'OLS')]
        var5_row = role_ols[role_ols['param'] == 'var5']
        if not var5_row.empty:
            se = var5_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n"
    
    # Panel B: IV
    table += r"""
\midrule
\multicolumn{9}{l}{\textbf{Panel B: IV}} \\
\addlinespace
"""
    
    # Panel B: IV - Remote × Post
    table += "Remote $\\times$ Post & "
    table += f"{format_coefficient(baseline_var3_iv, baseline_var3_iv_se, get_significance_stars(baseline_var3_iv, baseline_var3_iv_se))}"
    
    for role in roles:
        role_iv = df[(df['role'] == role) & (df['model_type'] == 'IV')]
        var3_row = role_iv[role_iv['param'] == 'var3']
        if not var3_row.empty:
            coef = var3_row['coef'].values[0]
            se = var3_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post
    table += " & " + format_se(baseline_var3_iv_se)
    for role in roles:
        role_iv = df[(df['role'] == role) & (df['model_type'] == 'IV')]
        var3_row = role_iv[role_iv['param'] == 'var3']
        if not var3_row.empty:
            se = var3_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n\\addlinespace[0.5em]\n"
    
    # Panel B: IV - Remote × Post × Startup
    table += "Remote $\\times$ Post $\\times$ Startup & "
    table += f"{format_coefficient(baseline_var5_iv, baseline_var5_iv_se, get_significance_stars(baseline_var5_iv, baseline_var5_iv_se))}"
    
    for role in roles:
        role_iv = df[(df['role'] == role) & (df['model_type'] == 'IV')]
        var5_row = role_iv[role_iv['param'] == 'var5']
        if not var5_row.empty:
            coef = var5_row['coef'].values[0]
            se = var5_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post × Startup
    table += " & " + format_se(baseline_var5_iv_se)
    for role in roles:
        role_iv = df[(df['role'] == role) & (df['model_type'] == 'IV')]
        var5_row = role_iv[role_iv['param'] == 'var5']
        if not var5_row.empty:
            se = var5_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n"
    
    # Sample sizes and F-stats
    table += r"""
\midrule
"""
    table += f"N & {baseline_n:,}"
    for role in roles:
        role_data = df[(df['role'] == role) & (df['model_type'] == 'OLS')]
        if not role_data.empty:
            n = int(role_data['nobs'].values[0])
            table += f" & {n:,}"
    table += " \\\\\n"
    
    table += f"KP rk Wald F & {baseline_rkf:.1f}"
    for role in roles:
        role_iv = df[(df['role'] == role) & (df['model_type'] == 'IV')]
        if not role_iv.empty:
            rkf = role_iv['rkf'].values[0]
            table += f" & {rkf:.1f}"
    table += " \\\\\n"
    
    # Control indicators
    table += r"""
\midrule
"""
    for i, role in enumerate(roles):
        table += f"{role} control & -"
        for j in range(len(roles)):
            if i == j:
                table += " & $\\checkmark$"
            else:
                table += " & -"
        table += " \\\\\n"
    
    table += r"""\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}
\small
\item \textit{Notes:} The dependent variable is user productivity (total contributions, 100th percentile winsorized). 
All specifications include worker-firm and time fixed effects. 
Composition controls are interactions of COVID $\times$ role growth $\times$ startup.
Standard errors clustered by user in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{table}"""
    
    return table

def create_seniority_table():
    """Create seniority composition effects table"""
    # Read seniority results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/user_productivity_composition/seniority_composition_results.csv')
    
    # Get baseline results
    baseline_ols = df[(df['seniority'] == 'Baseline') & (df['model_type'] == 'OLS')]
    baseline_iv = df[(df['seniority'] == 'Baseline') & (df['model_type'] == 'IV')]
    
    # Extract baseline coefficients
    baseline_var3_ols = baseline_ols[baseline_ols['param'] == 'var3']['coef'].values[0]
    baseline_var3_ols_se = baseline_ols[baseline_ols['param'] == 'var3']['se'].values[0]
    baseline_var5_ols = baseline_ols[baseline_ols['param'] == 'var5']['coef'].values[0]
    baseline_var5_ols_se = baseline_ols[baseline_ols['param'] == 'var5']['se'].values[0]
    
    baseline_var3_iv = baseline_iv[baseline_iv['param'] == 'var3']['coef'].values[0]
    baseline_var3_iv_se = baseline_iv[baseline_iv['param'] == 'var3']['se'].values[0]
    baseline_var5_iv = baseline_iv[baseline_iv['param'] == 'var5']['coef'].values[0]
    baseline_var5_iv_se = baseline_iv[baseline_iv['param'] == 'var5']['se'].values[0]
    
    baseline_n = int(baseline_ols['nobs'].values[0])
    baseline_rkf = baseline_iv['rkf'].values[0]
    
    # Seniority levels to process
    levels = ['Level_1', 'Level_2', 'Level_3', 'Level_4']
    
    # Start building table
    table = r"""\begin{table}[H]
\centering
\caption{Seniority Composition Effects on Remote Work Productivity}
\label{tab:seniority_composition}
\begin{tabular}{l*{5}{c}}
\toprule
 & (1) & (2) & (3) & (4) & (5) \\
\midrule
\multicolumn{6}{l}{\textbf{Panel A: OLS}} \\
\addlinespace
"""
    
    # Panel A: OLS - Remote × Post
    table += "Remote $\\times$ Post & "
    table += f"{format_coefficient(baseline_var3_ols, baseline_var3_ols_se, get_significance_stars(baseline_var3_ols, baseline_var3_ols_se))}"
    
    for level in levels:
        level_ols = df[(df['seniority'] == level) & (df['model_type'] == 'OLS')]
        var3_row = level_ols[level_ols['param'] == 'var3']
        if not var3_row.empty:
            coef = var3_row['coef'].values[0]
            se = var3_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post
    table += " & " + format_se(baseline_var3_ols_se)
    for level in levels:
        level_ols = df[(df['seniority'] == level) & (df['model_type'] == 'OLS')]
        var3_row = level_ols[level_ols['param'] == 'var3']
        if not var3_row.empty:
            se = var3_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n\\addlinespace[0.5em]\n"
    
    # Panel A: OLS - Remote × Post × Startup
    table += "Remote $\\times$ Post $\\times$ Startup & "
    table += f"{format_coefficient(baseline_var5_ols, baseline_var5_ols_se, get_significance_stars(baseline_var5_ols, baseline_var5_ols_se))}"
    
    for level in levels:
        level_ols = df[(df['seniority'] == level) & (df['model_type'] == 'OLS')]
        var5_row = level_ols[level_ols['param'] == 'var5']
        if not var5_row.empty:
            coef = var5_row['coef'].values[0]
            se = var5_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post × Startup
    table += " & " + format_se(baseline_var5_ols_se)
    for level in levels:
        level_ols = df[(df['seniority'] == level) & (df['model_type'] == 'OLS')]
        var5_row = level_ols[level_ols['param'] == 'var5']
        if not var5_row.empty:
            se = var5_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n"
    
    # Panel B: IV
    table += r"""
\midrule
\multicolumn{6}{l}{\textbf{Panel B: IV}} \\
\addlinespace
"""
    
    # Panel B: IV - Remote × Post
    table += "Remote $\\times$ Post & "
    table += f"{format_coefficient(baseline_var3_iv, baseline_var3_iv_se, get_significance_stars(baseline_var3_iv, baseline_var3_iv_se))}"
    
    for level in levels:
        level_iv = df[(df['seniority'] == level) & (df['model_type'] == 'IV')]
        var3_row = level_iv[level_iv['param'] == 'var3']
        if not var3_row.empty:
            coef = var3_row['coef'].values[0]
            se = var3_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post
    table += " & " + format_se(baseline_var3_iv_se)
    for level in levels:
        level_iv = df[(df['seniority'] == level) & (df['model_type'] == 'IV')]
        var3_row = level_iv[level_iv['param'] == 'var3']
        if not var3_row.empty:
            se = var3_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n\\addlinespace[0.5em]\n"
    
    # Panel B: IV - Remote × Post × Startup
    table += "Remote $\\times$ Post $\\times$ Startup & "
    table += f"{format_coefficient(baseline_var5_iv, baseline_var5_iv_se, get_significance_stars(baseline_var5_iv, baseline_var5_iv_se))}"
    
    for level in levels:
        level_iv = df[(df['seniority'] == level) & (df['model_type'] == 'IV')]
        var5_row = level_iv[level_iv['param'] == 'var5']
        if not var5_row.empty:
            coef = var5_row['coef'].values[0]
            se = var5_row['se'].values[0]
            table += f" & {format_coefficient(coef, se, get_significance_stars(coef, se))}"
    
    table += " \\\\\n"
    
    # Standard errors for Remote × Post × Startup
    table += " & " + format_se(baseline_var5_iv_se)
    for level in levels:
        level_iv = df[(df['seniority'] == level) & (df['model_type'] == 'IV')]
        var5_row = level_iv[level_iv['param'] == 'var5']
        if not var5_row.empty:
            se = var5_row['se'].values[0]
            table += f" & {format_se(se)}"
    table += " \\\\\n"
    
    # Sample sizes and F-stats
    table += r"""
\midrule
"""
    table += f"N & {baseline_n:,}"
    for level in levels:
        level_data = df[(df['seniority'] == level) & (df['model_type'] == 'OLS')]
        if not level_data.empty:
            n = int(level_data['nobs'].values[0])
            table += f" & {n:,}"
    table += " \\\\\n"
    
    table += f"KP rk Wald F & {baseline_rkf:.1f}"
    for level in levels:
        level_iv = df[(df['seniority'] == level) & (df['model_type'] == 'IV')]
        if not level_iv.empty:
            rkf = level_iv['rkf'].values[0]
            table += f" & {rkf:.1f}"
    table += " \\\\\n"
    
    # Control indicators
    table += r"""
\midrule
"""
    for i, level in enumerate(levels):
        table += f"{level.replace('_', ' ')} control & -"
        for j in range(len(levels)):
            if i == j:
                table += " & $\\checkmark$"
            else:
                table += " & -"
        table += " \\\\\n"
    
    table += r"""\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} The dependent variable is user productivity (total contributions, 100th percentile winsorized). 
All specifications include worker-firm and time fixed effects. 
Composition controls are interactions of COVID $\times$ seniority growth $\times$ startup.
Standard errors clustered by user in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{table}"""
    
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

\title{Workforce Composition and Remote Work Productivity}
\date{\today}

\begin{document}

\maketitle

\section{Introduction}

This analysis examines how changes in workforce composition moderate the remote work productivity effect at startups versus non-startups. We control for firm-level changes in the composition of workers by:
\begin{itemize}
\item Role (Admin, Engineer, Finance, Marketing, Operations, Sales, Scientist)
\item Seniority level (Levels 1-4)
\end{itemize}

The key variables are:
\begin{itemize}
\item Remote $\times$ Post: The effect of remote work post-COVID
\item Remote $\times$ Post $\times$ Startup: The differential effect for startups
\item Role/Seniority $\times$ COVID $\times$ Startup: The interaction with composition changes
\end{itemize}

\section{Role Composition Effects}

"""
    
    # Add role table
    doc += create_role_table()
    
    # Add seniority table
    doc += "\n\n\\section{Seniority Composition Effects}\n\n"
    doc += create_seniority_table()
    
    doc += "\n\n\\end{document}"
    
    return doc

if __name__ == "__main__":
    # Create LaTeX document
    latex_content = create_latex_document()
    
    # Write to file
    output_file = "/Users/saul/Dropbox/Remote Work Startups/main/writeup/composition_effects.tex"
    with open(output_file, 'w') as f:
        f.write(latex_content)
    
    print(f"LaTeX file created: {output_file}")