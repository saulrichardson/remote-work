#!/usr/bin/env python3
"""
Create LaTeX tables for binary composition with OLS and IV results
"""

import pandas as pd
import numpy as np

def format_coef(b, se, stars=''):
    """Format coefficient with standard error"""
    if pd.isna(b):
        return ""
    return f"{b:.3f}{stars}\\\\({se:.3f})"

def get_stars(b, se):
    """Determine significance stars"""
    if pd.isna(b) or pd.isna(se) or se == 0:
        return ''
    t = abs(b/se)
    if t > 2.58:
        return '***'
    elif t > 1.96:
        return '**'
    elif t > 1.64:
        return '*'
    return ''

# Read role results
try:
    role_df = pd.read_csv('results/raw/role_binary_ols_iv_results.csv')
    role_ols = role_df[role_df['model'] == 'OLS'].reset_index(drop=True)
    role_iv = role_df[role_df['model'] == 'IV'].reset_index(drop=True)
    
    # Create combined role table with OLS and IV
    role_table = r"""\begin{table}[H]
\centering
\caption{Remote Work Effects by Role Composition: OLS and IV}
\label{tab:scaling_roles_binary_ols_iv}
\tiny
\begin{adjustbox}{max width=\linewidth}
\begin{tabular}{l*{8}{c}}
\toprule
 & \multicolumn{2}{c}{Baseline} & \multicolumn{2}{c}{High Engineer} & \multicolumn{2}{c}{High Sales} & \multicolumn{2}{c}{High Finance} \\
 & OLS & IV & OLS & IV & OLS & IV & OLS & IV \\
\midrule
"""
    
    # Remote × Post
    role_table += "Remote × Post & "
    for i in range(4):  # First 4 roles
        if i < len(role_ols):
            # OLS
            b_ols = role_ols.loc[i, 'b_var3']
            se_ols = role_ols.loc[i, 'se_var3']
            stars_ols = get_stars(b_ols, se_ols)
            role_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = role_iv.loc[i, 'b_var3']
            se_iv = role_iv.loc[i, 'se_var3']
            stars_iv = get_stars(b_iv, se_iv)
            role_table += format_coef(b_iv, se_iv, stars_iv)
        role_table += " & " if i < 3 else " \\\\\n"
    
    # Remote × Post × Startup
    role_table += "[0.5ex]\nRemote × Post × Startup & "
    for i in range(4):
        if i < len(role_ols):
            # OLS
            b_ols = role_ols.loc[i, 'b_var5']
            se_ols = role_ols.loc[i, 'se_var5']
            stars_ols = get_stars(b_ols, se_ols)
            role_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = role_iv.loc[i, 'b_var5']
            se_iv = role_iv.loc[i, 'se_var5']
            stars_iv = get_stars(b_iv, se_iv)
            role_table += format_coef(b_iv, se_iv, stars_iv)
        role_table += " & " if i < 3 else " \\\\\n"
    
    # Binary interactions
    role_table += "[0.5ex]\nRemote × Post × High Role & & & "
    for i in range(1, 4):
        if i < len(role_ols):
            # OLS
            b_ols = role_ols.loc[i, 'b_int3']
            se_ols = role_ols.loc[i, 'se_int3']
            stars_ols = get_stars(b_ols, se_ols)
            role_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = role_iv.loc[i, 'b_int3']
            se_iv = role_iv.loc[i, 'se_int3']
            stars_iv = get_stars(b_iv, se_iv)
            role_table += format_coef(b_iv, se_iv, stars_iv)
        role_table += " & " if i < 3 else " \\\\\n"
    
    role_table += "[0.5ex]\nRemote × Post × Startup × High Role & & & "
    for i in range(1, 4):
        if i < len(role_ols):
            # OLS
            b_ols = role_ols.loc[i, 'b_int5']
            se_ols = role_ols.loc[i, 'se_int5']
            stars_ols = get_stars(b_ols, se_ols)
            role_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = role_iv.loc[i, 'b_int5']
            se_iv = role_iv.loc[i, 'se_int5']
            stars_iv = get_stars(b_iv, se_iv)
            role_table += format_coef(b_iv, se_iv, stars_iv)
        role_table += " & " if i < 3 else " \\\\\n"
    
    # Footer
    role_table += r"""\midrule
Observations & """
    for i in range(4):
        if i < len(role_ols):
            role_table += f"{int(role_ols.loc[i, 'n']):,} & {int(role_iv.loc[i, 'n']):,}"
        role_table += " & " if i < 3 else " \\\\\n"
    
    role_table += r"""Adj. R-sq / KP F-stat & """
    for i in range(4):
        if i < len(role_ols):
            role_table += f"{role_ols.loc[i, 'r2']:.3f} & {role_iv.loc[i, 'fstat']:.1f}"
        role_table += " & " if i < 3 else " \\\\\n"
    
    # Second part of table (remaining roles)
    role_table += r"""\midrule
 & \multicolumn{2}{c}{High Marketing} & \multicolumn{2}{c}{High Admin} & \multicolumn{2}{c}{High Operations} & \multicolumn{2}{c}{High Scientist} \\
 & OLS & IV & OLS & IV & OLS & IV & OLS & IV \\
\midrule
"""
    
    # Repeat for remaining roles (4-7)
    # Remote × Post
    role_table += "Remote × Post & "
    for i in range(4, 8):
        if i < len(role_ols):
            # OLS
            b_ols = role_ols.loc[i, 'b_var3']
            se_ols = role_ols.loc[i, 'se_var3']
            stars_ols = get_stars(b_ols, se_ols)
            role_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = role_iv.loc[i, 'b_var3']
            se_iv = role_iv.loc[i, 'se_var3']
            stars_iv = get_stars(b_iv, se_iv)
            role_table += format_coef(b_iv, se_iv, stars_iv)
        role_table += " & " if i < 7 else " \\\\\n"
    
    role_table += r"""\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}[flushleft]
\scriptsize
\item \textit{Notes:} Binary indicators for above-median role shares. OLS uses reghdfe, IV uses ivreghdfe with WFH exposure instruments. All specifications include firm and year-half fixed effects with clustered standard errors. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/scaling_roles_binary_ols_iv.tex', 'w') as f:
        f.write(role_table)
    
    print("Created: results/cleaned/scaling_roles_binary_ols_iv.tex")
    
except Exception as e:
    print(f"Error with role table: {e}")

# Read seniority results and create similar table
try:
    sen_df = pd.read_csv('results/raw/seniority_binary_ols_iv_results.csv')
    sen_ols = sen_df[sen_df['model'] == 'OLS'].reset_index(drop=True)
    sen_iv = sen_df[sen_df['model'] == 'IV'].reset_index(drop=True)
    
    # Create seniority table
    sen_table = r"""\begin{table}[H]
\centering
\caption{Remote Work Effects by Seniority Composition: OLS and IV}
\label{tab:scaling_seniority_binary_ols_iv}
\scriptsize
\begin{adjustbox}{max width=\linewidth}
\begin{tabular}{l*{10}{c}}
\toprule
 & \multicolumn{2}{c}{Baseline} & \multicolumn{2}{c}{High Entry} & \multicolumn{2}{c}{High Mid/Sr} & \multicolumn{2}{c}{High Manager} & \multicolumn{2}{c}{High Director} \\
 & OLS & IV & OLS & IV & OLS & IV & OLS & IV & OLS & IV \\
\midrule
"""
    
    # Remote × Post
    sen_table += "Remote × Post & "
    for i in range(5):
        if i < len(sen_ols):
            # OLS
            b_ols = sen_ols.loc[i, 'b_var3']
            se_ols = sen_ols.loc[i, 'se_var3']
            stars_ols = get_stars(b_ols, se_ols)
            sen_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = sen_iv.loc[i, 'b_var3']
            se_iv = sen_iv.loc[i, 'se_var3']
            stars_iv = get_stars(b_iv, se_iv)
            sen_table += format_coef(b_iv, se_iv, stars_iv)
        sen_table += " & " if i < 4 else " \\\\\n"
    
    # Remote × Post × Startup
    sen_table += "[0.5ex]\nRemote × Post × Startup & "
    for i in range(5):
        if i < len(sen_ols):
            # OLS
            b_ols = sen_ols.loc[i, 'b_var5']
            se_ols = sen_ols.loc[i, 'se_var5']
            stars_ols = get_stars(b_ols, se_ols)
            sen_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = sen_iv.loc[i, 'b_var5']
            se_iv = sen_iv.loc[i, 'se_var5']
            stars_iv = get_stars(b_iv, se_iv)
            sen_table += format_coef(b_iv, se_iv, stars_iv)
        sen_table += " & " if i < 4 else " \\\\\n"
    
    # Binary interactions
    sen_table += "[0.5ex]\nRemote × Post × High Sen. & & & "
    for i in range(1, 5):
        if i < len(sen_ols):
            # OLS
            b_ols = sen_ols.loc[i, 'b_int3']
            se_ols = sen_ols.loc[i, 'se_int3']
            stars_ols = get_stars(b_ols, se_ols)
            sen_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = sen_iv.loc[i, 'b_int3']
            se_iv = sen_iv.loc[i, 'se_int3']
            stars_iv = get_stars(b_iv, se_iv)
            sen_table += format_coef(b_iv, se_iv, stars_iv)
        sen_table += " & " if i < 4 else " \\\\\n"
    
    sen_table += "[0.5ex]\nRemote × Post × Startup × High Sen. & & & "
    for i in range(1, 5):
        if i < len(sen_ols):
            # OLS
            b_ols = sen_ols.loc[i, 'b_int5']
            se_ols = sen_ols.loc[i, 'se_int5']
            stars_ols = get_stars(b_ols, se_ols)
            sen_table += format_coef(b_ols, se_ols, stars_ols) + " & "
            
            # IV
            b_iv = sen_iv.loc[i, 'b_int5']
            se_iv = sen_iv.loc[i, 'se_int5']
            stars_iv = get_stars(b_iv, se_iv)
            sen_table += format_coef(b_iv, se_iv, stars_iv)
        sen_table += " & " if i < 4 else " \\\\\n"
    
    # Footer
    sen_table += r"""\midrule
Observations & """
    for i in range(5):
        if i < len(sen_ols):
            sen_table += f"{int(sen_ols.loc[i, 'n']):,} & {int(sen_iv.loc[i, 'n']):,}"
        sen_table += " & " if i < 4 else " \\\\\n"
    
    sen_table += r"""Adj. R-sq / KP F-stat & """
    for i in range(5):
        if i < len(sen_ols):
            sen_table += f"{sen_ols.loc[i, 'r2']:.3f} & {sen_iv.loc[i, 'fstat']:.1f}"
        sen_table += " & " if i < 4 else " \\\\\n"
    
    sen_table += r"""\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}[flushleft]
\scriptsize
\item \textit{Notes:} Binary indicators for above-median seniority shares. Level 1 = Entry, Level 2 = Mid/Senior IC, Level 3 = Manager, Level 4 = Director+. OLS uses reghdfe, IV uses ivreghdfe with WFH exposure instruments. All specifications include firm and year-half fixed effects with clustered standard errors. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/scaling_seniority_binary_ols_iv.tex', 'w') as f:
        f.write(sen_table)
    
    print("Created: results/cleaned/scaling_seniority_binary_ols_iv.tex")
    
except Exception as e:
    print(f"Error with seniority table: {e}")

# Create standalone document
standalone = r"""\documentclass{article}
\usepackage{booktabs}
\usepackage{adjustbox}
\usepackage{threeparttable}
\usepackage{amsmath}
\usepackage{float}
\usepackage[margin=0.75in]{geometry}

\title{Remote Work Effects by Workforce Composition\\OLS and IV Results with Binary Indicators}
\date{\today}

\begin{document}
\maketitle

\section{Role Composition}
\input{scaling_roles_binary_ols_iv.tex}

\clearpage
\section{Seniority Composition}
\input{scaling_seniority_binary_ols_iv.tex}

\end{document}"""

with open('results/cleaned/scaling_composition_binary_ols_iv_all.tex', 'w') as f:
    f.write(standalone)

print("Created: results/cleaned/scaling_composition_binary_ols_iv_all.tex")