#!/usr/bin/env python3
"""
Format firm scaling composition results (roles and seniority) into LaTeX tables
"""
import pandas as pd
import numpy as np

def format_coefficient(coef, se, stars=''):
    """Format coefficient with standard error"""
    return f"{coef:.2f}{stars}"

def format_se(se):
    """Format standard error in parentheses"""
    return f"({se:.2f})"

def get_significance_stars(pval):
    """Get significance stars based on p-value"""
    if pd.isna(pval):
        return ''
    if pval <= 0.01:
        return '***'
    elif pval <= 0.05:
        return '**'
    elif pval <= 0.10:
        return '*'
    return ''

def create_role_composition_table():
    """Create role composition effects table for firm scaling"""
    # Read role results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/scaling_composition_roles/role_scaling_share_results.csv')
    
    # Define role order
    roles = ['Admin', 'Engineer', 'Finance', 'Marketing', 'Operations', 'Sales', 'Scientist']
    
    # Initialize results dictionary
    results = {}
    
    for role in roles:
        # Filter for this role
        role_df = df[df['role'] == role]
        
        if not role_df.empty:
            # OLS results
            ols_df = role_df[role_df['model_type'] == 'OLS']
            ols_var3 = ols_df[ols_df['param'] == 'var3'].iloc[0] if not ols_df[ols_df['param'] == 'var3'].empty else None
            ols_var5 = ols_df[ols_df['param'] == 'var5'].iloc[0] if not ols_df[ols_df['param'] == 'var5'].empty else None
            
            # IV results
            iv_df = role_df[role_df['model_type'] == 'IV']
            iv_var3 = iv_df[iv_df['param'] == 'var3'].iloc[0] if not iv_df[iv_df['param'] == 'var3'].empty else None
            iv_var5 = iv_df[iv_df['param'] == 'var5'].iloc[0] if not iv_df[iv_df['param'] == 'var5'].empty else None
            
            # Store results
            if ols_var3 is not None:
                results[f'{role}_ols_var3_coef'] = ols_var3['coef']
                results[f'{role}_ols_var3_se'] = ols_var3['se']
                results[f'{role}_ols_var3_pval'] = ols_var3['pval']
                results[f'{role}_nobs'] = int(ols_var3['nobs'])
            
            if ols_var5 is not None:
                results[f'{role}_ols_var5_coef'] = ols_var5['coef']
                results[f'{role}_ols_var5_se'] = ols_var5['se']
                results[f'{role}_ols_var5_pval'] = ols_var5['pval']
            
            if iv_var3 is not None:
                results[f'{role}_iv_var3_coef'] = iv_var3['coef']
                results[f'{role}_iv_var3_se'] = iv_var3['se']
                results[f'{role}_iv_var3_pval'] = iv_var3['pval']
                results[f'{role}_rkf'] = iv_var3['rkf']
            
            if iv_var5 is not None:
                results[f'{role}_iv_var5_coef'] = iv_var5['coef']
                results[f'{role}_iv_var5_se'] = iv_var5['se']
                results[f'{role}_iv_var5_pval'] = iv_var5['pval']
    
    # Create table
    table = r"""\begin{table}[H]
\centering
\caption{Role Composition Effects on Firm Scaling}
\begin{threeparttable}
\begin{adjustbox}{width=\textwidth}
\begin{tabular}{lccccccc}
\toprule
 & (1) & (2) & (3) & (4) & (5) & (6) & (7) \\
 & Admin & Engineer & Finance & Marketing & Operations & Sales & Scientist \\
\midrule
\multicolumn{8}{l}{\textbf{Panel A: OLS}} \\
\addlinespace
Remote $\times$ Post"""
    
    # Add OLS var3 coefficients
    for role in roles:
        if f'{role}_ols_var3_coef' in results:
            coef = results[f'{role}_ols_var3_coef']
            pval = results[f'{role}_ols_var3_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add OLS var3 standard errors
    table += "\n "
    for role in roles:
        if f'{role}_ols_var3_se' in results:
            se = results[f'{role}_ols_var3_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup"""
    
    # Add OLS var5 coefficients
    for role in roles:
        if f'{role}_ols_var5_coef' in results:
            coef = results[f'{role}_ols_var5_coef']
            pval = results[f'{role}_ols_var5_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add OLS var5 standard errors
    table += "\n "
    for role in roles:
        if f'{role}_ols_var5_se' in results:
            se = results[f'{role}_ols_var5_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\midrule
\multicolumn{8}{l}{\textbf{Panel B: IV}} \\
\addlinespace
Remote $\times$ Post"""
    
    # Add IV var3 coefficients
    for role in roles:
        if f'{role}_iv_var3_coef' in results:
            coef = results[f'{role}_iv_var3_coef']
            pval = results[f'{role}_iv_var3_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add IV var3 standard errors
    table += "\n "
    for role in roles:
        if f'{role}_iv_var3_se' in results:
            se = results[f'{role}_iv_var3_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup"""
    
    # Add IV var5 coefficients
    for role in roles:
        if f'{role}_iv_var5_coef' in results:
            coef = results[f'{role}_iv_var5_coef']
            pval = results[f'{role}_iv_var5_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add IV var5 standard errors
    table += "\n "
    for role in roles:
        if f'{role}_iv_var5_se' in results:
            se = results[f'{role}_iv_var5_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\midrule
N"""
    
    # Add N
    for role in roles:
        if f'{role}_nobs' in results:
            n = results[f'{role}_nobs']
            table += f" & {n:,}"
        else:
            table += " & -"
    
    table += r" \\"
    table += "\nKP rk Wald F"
    
    # Add KP rk Wald F
    for role in roles:
        if f'{role}_rkf' in results:
            rkf = results[f'{role}_rkf']
            table += f" & {rkf:.1f}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}
\small
\item \textit{Notes:} Firm-level regressions with firm and time fixed effects. 
Dependent variable is share of role-specific employment in the firm workforce. 
Remote is an indicator for remote-first firms. Post indicates post-COVID periods.
Startup indicates young, high-growth firms.
Standard errors clustered by firm in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{threeparttable}
\end{table}"""
    
    return table

def create_seniority_composition_table():
    """Create seniority composition effects table for firm scaling"""
    # Read seniority results
    df = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/scaling_composition_seniority/seniority_scaling_share_results.csv')
    
    # Define seniority levels
    levels = ['Level_1', 'Level_2', 'Level_3', 'Level_4']
    
    # Initialize results dictionary
    results = {}
    
    for level in levels:
        # Filter for this level
        level_df = df[df['seniority'] == level]
        
        if not level_df.empty:
            # OLS results
            ols_df = level_df[level_df['model_type'] == 'OLS']
            ols_var3 = ols_df[ols_df['param'] == 'var3'].iloc[0] if not ols_df[ols_df['param'] == 'var3'].empty else None
            ols_var5 = ols_df[ols_df['param'] == 'var5'].iloc[0] if not ols_df[ols_df['param'] == 'var5'].empty else None
            
            # IV results
            iv_df = level_df[level_df['model_type'] == 'IV']
            iv_var3 = iv_df[iv_df['param'] == 'var3'].iloc[0] if not iv_df[iv_df['param'] == 'var3'].empty else None
            iv_var5 = iv_df[iv_df['param'] == 'var5'].iloc[0] if not iv_df[iv_df['param'] == 'var5'].empty else None
            
            # Store results
            if ols_var3 is not None:
                results[f'{level}_ols_var3_coef'] = ols_var3['coef']
                results[f'{level}_ols_var3_se'] = ols_var3['se']
                results[f'{level}_ols_var3_pval'] = ols_var3['pval']
                results[f'{level}_nobs'] = int(ols_var3['nobs'])
            
            if ols_var5 is not None:
                results[f'{level}_ols_var5_coef'] = ols_var5['coef']
                results[f'{level}_ols_var5_se'] = ols_var5['se']
                results[f'{level}_ols_var5_pval'] = ols_var5['pval']
            
            if iv_var3 is not None:
                results[f'{level}_iv_var3_coef'] = iv_var3['coef']
                results[f'{level}_iv_var3_se'] = iv_var3['se']
                results[f'{level}_iv_var3_pval'] = iv_var3['pval']
                results[f'{level}_rkf'] = iv_var3['rkf']
            
            if iv_var5 is not None:
                results[f'{level}_iv_var5_coef'] = iv_var5['coef']
                results[f'{level}_iv_var5_se'] = iv_var5['se']
                results[f'{level}_iv_var5_pval'] = iv_var5['pval']
    
    # Create table
    table = r"""\begin{table}[H]
\centering
\caption{Seniority Composition Effects on Firm Scaling}
\begin{threeparttable}
\begin{tabular}{lcccc}
\toprule
 & (1) & (2) & (3) & (4) \\
 & Level 1 & Level 2 & Level 3 & Level 4 \\
\midrule
\multicolumn{5}{l}{\textbf{Panel A: OLS}} \\
\addlinespace
Remote $\times$ Post"""
    
    # Add OLS var3 coefficients
    for level in levels:
        if f'{level}_ols_var3_coef' in results:
            coef = results[f'{level}_ols_var3_coef']
            pval = results[f'{level}_ols_var3_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add OLS var3 standard errors
    table += "\n "
    for level in levels:
        if f'{level}_ols_var3_se' in results:
            se = results[f'{level}_ols_var3_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup"""
    
    # Add OLS var5 coefficients
    for level in levels:
        if f'{level}_ols_var5_coef' in results:
            coef = results[f'{level}_ols_var5_coef']
            pval = results[f'{level}_ols_var5_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add OLS var5 standard errors
    table += "\n "
    for level in levels:
        if f'{level}_ols_var5_se' in results:
            se = results[f'{level}_ols_var5_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\midrule
\multicolumn{5}{l}{\textbf{Panel B: IV}} \\
\addlinespace
Remote $\times$ Post"""
    
    # Add IV var3 coefficients
    for level in levels:
        if f'{level}_iv_var3_coef' in results:
            coef = results[f'{level}_iv_var3_coef']
            pval = results[f'{level}_iv_var3_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add IV var3 standard errors
    table += "\n "
    for level in levels:
        if f'{level}_iv_var3_se' in results:
            se = results[f'{level}_iv_var3_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup"""
    
    # Add IV var5 coefficients
    for level in levels:
        if f'{level}_iv_var5_coef' in results:
            coef = results[f'{level}_iv_var5_coef']
            pval = results[f'{level}_iv_var5_pval']
            stars = get_significance_stars(pval)
            table += f" & {format_coefficient(coef, 0, stars)}"
        else:
            table += " & -"
    
    table += r" \\"
    
    # Add IV var5 standard errors
    table += "\n "
    for level in levels:
        if f'{level}_iv_var5_se' in results:
            se = results[f'{level}_iv_var5_se']
            table += f" & {format_se(se)}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\midrule
N"""
    
    # Add N
    for level in levels:
        if f'{level}_nobs' in results:
            n = results[f'{level}_nobs']
            table += f" & {n:,}"
        else:
            table += " & -"
    
    table += r" \\"
    table += "\nKP rk Wald F"
    
    # Add KP rk Wald F
    for level in levels:
        if f'{level}_rkf' in results:
            rkf = results[f'{level}_rkf']
            table += f" & {rkf:.1f}"
        else:
            table += " & -"
    
    table += r" \\"
    table += r"""
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} Firm-level regressions with firm and time fixed effects. 
Dependent variable is share of seniority-specific employment in the firm workforce. 
Seniority levels: 1 (most junior) to 4 (most senior).
Remote is an indicator for remote-first firms. Post indicates post-COVID periods.
Startup indicates young, high-growth firms.
Standard errors clustered by firm in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{threeparttable}
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

\title{Firm Composition Effects on Scaling}
\date{\today}

\begin{document}

\maketitle

\section{Introduction}

Firm scaling regressions with composition share levels as outcomes. Specifications test whether remote firms maintain different workforce composition in roles and seniority post-COVID.

"""
    
    # Add role composition table
    doc += "\n\\section{Role Composition Effects}\n\n"
    doc += create_role_composition_table()
    
    # Add seniority composition table  
    doc += "\n\n\\section{Seniority Composition Effects}\n\n"
    doc += create_seniority_composition_table()
    
    doc += "\n\n\\end{document}"
    
    return doc

def verify_results():
    """Print sample of results to verify against log files"""
    print("Verifying Role Results:")
    df_role = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/scaling_composition_roles/role_scaling_share_results.csv')
    print("\nSample of role data (first 5 rows):")
    print(df_role.head())
    print(f"\nTotal rows in role data: {len(df_role)}")
    
    print("\n\nVerifying Seniority Results:")
    df_sen = pd.read_csv('/Users/saul/Dropbox/Remote Work Startups/main/results/raw/scaling_composition_seniority/seniority_scaling_share_results.csv')
    print("\nSample of seniority data (first 5 rows):")
    print(df_sen.head())
    print(f"\nTotal rows in seniority data: {len(df_sen)}")

if __name__ == "__main__":
    # First verify the data
    verify_results()
    
    # Create LaTeX document
    latex_content = create_latex_document()
    
    # Write to file
    output_file = "/Users/saul/Dropbox/Remote Work Startups/main/writeup/scaling_composition_tables.tex"
    with open(output_file, 'w') as f:
        f.write(latex_content)
    
    print(f"\nLaTeX file created: {output_file}")
    
    # Also save individual tables
    with open("/Users/saul/Dropbox/Remote Work Startups/main/results/cleaned/scaling_role_composition_table.tex", 'w') as f:
        f.write(create_role_composition_table())
    
    with open("/Users/saul/Dropbox/Remote Work Startups/main/results/cleaned/scaling_seniority_composition_table.tex", 'w') as f:
        f.write(create_seniority_composition_table())
    
    print("Individual table files also created in results/cleaned/")
