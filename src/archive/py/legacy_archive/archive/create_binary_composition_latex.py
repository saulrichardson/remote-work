#!/usr/bin/env python3
"""
Create clean LaTeX tables for BINARY role and seniority composition results
"""

import pandas as pd
import numpy as np

def format_coef(b, se, stars=''):
    """Format coefficient with standard error"""
    if pd.isna(b):
        return ""
    return f"{b:.3f}{stars}\n({se:.3f})"

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
    role_df = pd.read_csv('results/raw/role_binary_results.csv')
    
    # Create role table
    role_table = r"""\begin{table}[H]
\centering
\caption{Remote Work Effects by Role Composition (Binary Indicators)}
\label{tab:scaling_roles_binary}
\scriptsize
\begin{adjustbox}{max width=\linewidth}
\begin{tabular}{l*{8}{c}}
\toprule
 & (1) & (2) & (3) & (4) & (5) & (6) & (7) & (8) \\
 & Baseline & High Eng. & High Sales & High Fin. & High Mkt. & High Admin & High Ops. & High Sci. \\
\midrule
"""
    
    # Remote × Post row
    role_table += "Remote × Post & "
    for i in range(8):
        if i < len(role_df):
            b = role_df.loc[i, 'b_var3']
            se = role_df.loc[i, 'se_var3']
            stars = get_stars(b, se)
            role_table += format_coef(b, se, stars).replace('\n', ' ')
        role_table += " & " if i < 7 else " \\\\\n"
    
    # Remote × Post × Startup row
    role_table += "Remote × Post × Startup & "
    for i in range(8):
        if i < len(role_df):
            b = role_df.loc[i, 'b_var5']
            se = role_df.loc[i, 'se_var5']
            stars = get_stars(b, se)
            role_table += format_coef(b, se, stars).replace('\n', ' ')
        role_table += " & " if i < 7 else " \\\\\n"
    
    # Binary interaction rows
    role_table += "[0.5ex]\n"
    role_table += "Remote × Post × High Role & & "
    for i in range(1, 8):
        if i < len(role_df):
            b = role_df.loc[i, 'b_int3']
            se = role_df.loc[i, 'se_int3']
            stars = get_stars(b, se)
            role_table += format_coef(b, se, stars).replace('\n', ' ')
        role_table += " & " if i < 7 else " \\\\\n"
    
    role_table += "Remote × Post × Startup × High Role & & "
    for i in range(1, 8):
        if i < len(role_df):
            b = role_df.loc[i, 'b_int5']
            se = role_df.loc[i, 'se_int5']
            stars = get_stars(b, se)
            role_table += format_coef(b, se, stars).replace('\n', ' ')
        role_table += " & " if i < 7 else " \\\\\n"
    
    # Footer
    role_table += r"""\midrule
Observations & """
    for i in range(8):
        if i < len(role_df):
            role_table += f"{int(role_df.loc[i, 'n']):,}"
        role_table += " & " if i < 7 else " \\\\\n"
    
    role_table += r"""Adj. R-squared & """
    for i in range(8):
        if i < len(role_df):
            role_table += f"{role_df.loc[i, 'r2']:.3f}"
        role_table += " & " if i < 7 else " \\\\\n"
    
    role_table += r"""\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}[flushleft]
\scriptsize
\item \textit{Notes:} Each column tests whether firms with above-median share of workers in that role experience different remote work effects. "High" indicates above-median pre-COVID (2019) share. All specifications include firm and year-half fixed effects with standard errors clustered at the firm level. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/scaling_roles_binary.tex', 'w') as f:
        f.write(role_table)
    
    print("Created: results/cleaned/scaling_roles_binary.tex")
    
except Exception as e:
    print(f"Error with role table: {e}")

# Read seniority results
try:
    sen_df = pd.read_csv('results/raw/seniority_binary_results.csv')
    
    # Create seniority table
    sen_table = r"""\begin{table}[H]
\centering
\caption{Remote Work Effects by Seniority Composition (Binary Indicators)}
\label{tab:scaling_seniority_binary}
\scriptsize
\begin{tabular}{l*{5}{c}}
\toprule
 & (1) & (2) & (3) & (4) & (5) \\
 & Baseline & High Entry & High Mid/Sr & High Manager & High Director \\
\midrule
"""
    
    # Remote × Post row
    sen_table += "Remote × Post & "
    for i in range(5):
        if i < len(sen_df):
            b = sen_df.loc[i, 'b_var3']
            se = sen_df.loc[i, 'se_var3']
            stars = get_stars(b, se)
            sen_table += format_coef(b, se, stars).replace('\n', ' ')
        sen_table += " & " if i < 4 else " \\\\\n"
    
    # Remote × Post × Startup row
    sen_table += "Remote × Post × Startup & "
    for i in range(5):
        if i < len(sen_df):
            b = sen_df.loc[i, 'b_var5']
            se = sen_df.loc[i, 'se_var5']
            stars = get_stars(b, se)
            sen_table += format_coef(b, se, stars).replace('\n', ' ')
        sen_table += " & " if i < 4 else " \\\\\n"
    
    # Binary interaction rows
    sen_table += "[0.5ex]\n"
    sen_table += "Remote × Post × High Seniority & & "
    for i in range(1, 5):
        if i < len(sen_df):
            b = sen_df.loc[i, 'b_int3']
            se = sen_df.loc[i, 'se_int3']
            stars = get_stars(b, se)
            sen_table += format_coef(b, se, stars).replace('\n', ' ')
        sen_table += " & " if i < 4 else " \\\\\n"
    
    sen_table += "Remote × Post × Startup × High Seniority & & "
    for i in range(1, 5):
        if i < len(sen_df):
            b = sen_df.loc[i, 'b_int5']
            se = sen_df.loc[i, 'se_int5']
            stars = get_stars(b, se)
            sen_table += format_coef(b, se, stars).replace('\n', ' ')
        sen_table += " & " if i < 4 else " \\\\\n"
    
    # Footer
    sen_table += r"""\midrule
Observations & """
    for i in range(5):
        if i < len(sen_df):
            sen_table += f"{int(sen_df.loc[i, 'n']):,}"
        sen_table += " & " if i < 4 else " \\\\\n"
    
    sen_table += r"""Adj. R-squared & """
    for i in range(5):
        if i < len(sen_df):
            sen_table += f"{sen_df.loc[i, 'r2']:.3f}"
        sen_table += " & " if i < 4 else " \\\\\n"
    
    sen_table += r"""\bottomrule
\end{tabular}
\begin{tablenotes}[flushleft]
\scriptsize
\item \textit{Notes:} Each column tests whether firms with above-median share of workers at that seniority level experience different remote work effects. "High" indicates above-median pre-COVID (2019) share. Level 1 = Entry, Level 2 = Mid/Senior IC, Level 3 = Manager, Level 4 = Director+. All specifications include firm and year-half fixed effects with standard errors clustered at the firm level. *** p$<$0.01, ** p$<$0.05, * p$<$0.10.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/scaling_seniority_binary.tex', 'w') as f:
        f.write(sen_table)
    
    print("Created: results/cleaned/scaling_seniority_binary.tex")
    
except Exception as e:
    print(f"Error with seniority table: {e}")

# Create OLS/IV comparison table
try:
    ols_iv_df = pd.read_csv('results/raw/scaling_binary_ols_iv.csv')
    
    # Create comparison table
    comp_table = r"""\begin{table}[H]
\centering
\caption{OLS vs IV: Remote Work Effects by Binary Composition}
\label{tab:scaling_binary_ols_iv}
\scriptsize
\begin{adjustbox}{max width=\linewidth}
\begin{tabular}{lcccccc}
\toprule
 & \multicolumn{3}{c}{OLS (reghdfe)} & \multicolumn{3}{c}{IV (ivreghdfe)} \\
\cmidrule(lr){2-4} \cmidrule(lr){5-7}
 & (1) & (2) & (3) & (4) & (5) & (6) \\
 & Baseline & High Eng. & High Sales & Baseline & High Eng. & High Sales \\
\midrule
Remote × Post & -0.001 & -0.001 & 0.001 & 0.003 & TBD & TBD \\
 & (0.005) & (0.005) & (0.005) & (0.008) & & \\
Remote × Post × Startup & 0.079*** & 0.081*** & 0.064** & 0.106 & TBD & TBD \\
 & (0.025) & (0.025) & (0.026) & (0.091) & & \\
Remote × Post × High Role & & -0.001 & -0.028*** & & TBD & TBD \\
 & & (0.006) & (0.007) & & & \\
Remote × Post × Startup × High Role & & -0.004 & 0.027 & & TBD & TBD \\
 & & (0.030) & (0.030) & & & \\
\midrule
Observations & 39,660 & 39,660 & 39,660 & 39,660 & 39,660 & 39,660 \\
Adj. R-squared & 0.324 & 0.324 & 0.326 & -- & -- & -- \\
KP F-statistic & -- & -- & -- & 17.3 & TBD & TBD \\
\bottomrule
\end{tabular}
\end{adjustbox}
\begin{tablenotes}[flushleft]
\scriptsize
\item \textit{Notes:} Binary indicators for "High" = above median share. Standard errors clustered at firm level.
\end{tablenotes}
\end{table}"""
    
    with open('results/cleaned/scaling_binary_ols_iv_comp.tex', 'w') as f:
        f.write(comp_table)
    
    print("Created: results/cleaned/scaling_binary_ols_iv_comp.tex")
    
except Exception as e:
    print(f"Error with OLS/IV table: {e}")

# Create standalone document
standalone = r"""\documentclass{article}
\usepackage{booktabs}
\usepackage{adjustbox}
\usepackage{threeparttable}
\usepackage{amsmath}
\usepackage{float}
\usepackage[margin=0.75in]{geometry}

\title{Remote Work Effects by Workforce Composition\\(Binary Indicators)}
\date{\today}

\begin{document}
\maketitle

\section{Role Composition}
\input{scaling_roles_binary.tex}

\vspace{0.5cm}

\section{Seniority Composition}
\input{scaling_seniority_binary.tex}

\end{document}"""

with open('results/cleaned/scaling_composition_binary_all.tex', 'w') as f:
    f.write(standalone)

print("Created: results/cleaned/scaling_composition_binary_all.tex")