#!/usr/bin/env python3
"""
Create clean, focused LaTeX tables for binary composition results
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

# Read results
try:
    role_df = pd.read_csv('results/raw/role_binary_ols_iv_results.csv')
    sen_df = pd.read_csv('results/raw/seniority_binary_ols_iv_results.csv')
    
    # Create KEY ROLES table (Engineer, Sales, Marketing only)
    key_roles_table = r"""\begin{table}[H]
\centering
\caption{Remote Work Effects by Key Role Composition (Binary)}
\label{tab:key_roles_binary}
\small
\begin{tabular}{lccc|ccc}
\toprule
 & \multicolumn{3}{c}{OLS (reghdfe)} & \multicolumn{3}{c}{IV (ivreghdfe)} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-7}
 & Engineer & Sales & Marketing & Engineer & Sales & Marketing \\
 & High & High & High & High & High & High \\
\midrule
Remote × Post & """
    
    # Get OLS and IV results for key roles
    role_ols = role_df[role_df['model'] == 'OLS'].reset_index(drop=True)
    role_iv = role_df[role_df['model'] == 'IV'].reset_index(drop=True)
    
    # Key roles: Engineer (index 1), Sales (index 2), Marketing (index 4)
    key_indices = [1, 2, 4]
    
    # Remote × Post row
    for idx in key_indices:
        b = role_ols.loc[idx, 'b_var3']
        se = role_ols.loc[idx, 'se_var3']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " & "
    
    for idx in key_indices:
        b = role_iv.loc[idx, 'b_var3']
        se = role_iv.loc[idx, 'se_var3']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " \\\\\n"
    
    # Remote × Post × Startup row
    key_roles_table += "Remote × Post × Startup & "
    for idx in key_indices:
        b = role_ols.loc[idx, 'b_var5']
        se = role_ols.loc[idx, 'se_var5']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " & "
    
    for idx in key_indices:
        b = role_iv.loc[idx, 'b_var5']
        se = role_iv.loc[idx, 'se_var5']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " \\\\\n"
    
    # High Role interaction
    key_roles_table += "[0.5ex]\nRemote × Post × High Role & "
    for idx in key_indices:
        b = role_ols.loc[idx, 'b_int3']
        se = role_ols.loc[idx, 'se_int3']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " & "
    
    for idx in key_indices:
        b = role_iv.loc[idx, 'b_int3']
        se = role_iv.loc[idx, 'se_int3']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " \\\\\n"
    
    # Startup × High Role interaction
    key_roles_table += "Remote × Post × Startup × High Role & "
    for idx in key_indices:
        b = role_ols.loc[idx, 'b_int5']
        se = role_ols.loc[idx, 'se_int5']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " & "
    
    for idx in key_indices:
        b = role_iv.loc[idx, 'b_int5']
        se = role_iv.loc[idx, 'se_int5']
        stars = get_stars(b, se)
        key_roles_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    
    key_roles_table = key_roles_table[:-2] + " \\\\\n"
    
    # Footer
    key_roles_table += r"""\midrule
Observations & 39,660 & 39,660 & 39,660 & 39,660 & 39,660 & 39,660 \\
Adj. R-sq / KP F-stat & """
    
    for idx in key_indices:
        key_roles_table += f"{role_ols.loc[idx, 'r2']:.3f} & "
    key_roles_table = key_roles_table[:-2] + " & "
    
    for idx in key_indices:
        key_roles_table += f"{role_iv.loc[idx, 'fstat']:.1f} & "
    key_roles_table = key_roles_table[:-2] + " \\\\\n"
    
    key_roles_table += r"""\bottomrule
\end{tabular}
\begin{tablenotes}[flushleft]
\small
\item \textit{Notes:} "High" indicates above-median share of workers in that role (pre-COVID 2019). All specifications include firm and year-half fixed effects with standard errors clustered at firm level. IV specifications instrument remote work with pre-determined WFH exposure. KP F-stat is the Kleibergen-Paap weak identification statistic. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/key_roles_binary_clean.tex', 'w') as f:
        f.write(key_roles_table)
    
    print("Created: results/cleaned/key_roles_binary_clean.tex")
    
    # Create SENIORITY table (simpler format)
    sen_ols = sen_df[sen_df['model'] == 'OLS'].reset_index(drop=True)
    sen_iv = sen_df[sen_df['model'] == 'IV'].reset_index(drop=True)
    
    sen_table = r"""\begin{table}[H]
\centering
\caption{Remote Work Effects by Seniority Composition (Binary)}
\label{tab:seniority_binary_clean}
\small
\begin{tabular}{lcccc}
\toprule
 & Entry & Mid/Senior & Manager & Director+ \\
 & Level (L1) & IC (L2) & (L3) & (L4) \\
\midrule
\multicolumn{5}{l}{\textit{Panel A: OLS Results}} \\
Remote × Post × High Seniority & """
    
    # OLS interactions only (cleaner presentation)
    for i in range(1, 5):
        b = sen_ols.loc[i, 'b_int3']
        se = sen_ols.loc[i, 'se_int3']
        stars = get_stars(b, se)
        sen_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    sen_table = sen_table[:-2] + " \\\\\n"
    
    sen_table += "Remote × Post × Startup × High Sen. & "
    for i in range(1, 5):
        b = sen_ols.loc[i, 'b_int5']
        se = sen_ols.loc[i, 'se_int5']
        stars = get_stars(b, se)
        sen_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    sen_table = sen_table[:-2] + " \\\\\n"
    
    sen_table += r"""[0.5ex]
\multicolumn{5}{l}{\textit{Panel B: IV Results}} \\
Remote × Post × High Seniority & """
    
    # IV interactions
    for i in range(1, 5):
        b = sen_iv.loc[i, 'b_int3']
        se = sen_iv.loc[i, 'se_int3']
        stars = get_stars(b, se)
        sen_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    sen_table = sen_table[:-2] + " \\\\\n"
    
    sen_table += "Remote × Post × Startup × High Sen. & "
    for i in range(1, 5):
        b = sen_iv.loc[i, 'b_int5']
        se = sen_iv.loc[i, 'se_int5']
        stars = get_stars(b, se)
        sen_table += format_coef(b, se, stars).replace('\\\\', '\n') + " & "
    sen_table = sen_table[:-2] + " \\\\\n"
    
    sen_table += r"""\midrule
Observations (each model) & \multicolumn{4}{c}{39,660} \\
KP F-statistic (IV models) & """
    
    for i in range(1, 5):
        sen_table += f"{sen_iv.loc[i, 'fstat']:.1f} & "
    sen_table = sen_table[:-2] + " \\\\\n"
    
    sen_table += r"""\bottomrule
\end{tabular}
\begin{tablenotes}[flushleft]
\small
\item \textit{Notes:} "High" indicates above-median share at that seniority level. Table shows interaction coefficients only; main effects of Remote × Post are similar across specifications (OLS: -0.001, IV: 0.003-0.009). All models include firm and year-half fixed effects. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/seniority_binary_clean.tex', 'w') as f:
        f.write(sen_table)
    
    print("Created: results/cleaned/seniority_binary_clean.tex")
    
except Exception as e:
    print(f"Error: {e}")

# Create standalone document
standalone = r"""\documentclass{article}
\usepackage{booktabs}
\usepackage{threeparttable}
\usepackage{amsmath}
\usepackage{float}
\usepackage[margin=1in]{geometry}

\title{Remote Work Effects by Workforce Composition\\Clean Binary Results}
\date{\today}

\begin{document}
\maketitle

\section{Key Role Composition}

This table focuses on the three most important roles: Engineers, Sales, and Marketing.

\input{key_roles_binary_clean.tex}

\section{Seniority Composition}

This table shows how seniority structure affects remote work effectiveness.

\input{seniority_binary_clean.tex}

\section{Key Findings}

\subsection{Role Composition}
\begin{itemize}
\item \textbf{Sales-heavy firms}: Struggle with remote work in OLS (-0.028***) and IV (-0.044***)
\item \textbf{Engineer-heavy firms}: No significant differential effect
\item \textbf{Marketing-heavy firms}: Mixed results (negative in OLS, not significant in IV)
\end{itemize}

\subsection{Seniority Composition}
\begin{itemize}
\item \textbf{Entry-heavy firms}: Some evidence of struggles with remote (IV: -0.015**)
\item \textbf{Mid/Senior IC heavy}: No consistent effects
\item \textbf{Management-heavy}: Generally positive but not always significant
\end{itemize}

\end{document}"""

with open('results/cleaned/composition_binary_clean_all.tex', 'w') as f:
    f.write(standalone)

print("Created: results/cleaned/composition_binary_clean_all.tex")