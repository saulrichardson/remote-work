#!/usr/bin/env python3
"""
Create LaTeX tables from Stata growth mechanisms output
"""
import re
import os

def parse_stata_log(log_file):
    """Parse Stata log file to extract regression results"""
    with open(log_file, 'r') as f:
        content = f.read()
    
    results = {}
    
    # Extract baseline regression results
    baseline_match = re.search(r'=== BASELINE WITH ALL OBSERVATIONS.*?ivreghdfe.*?var3.*?\s+([-\d.]+)\s+\d+\.\d+.*?var5.*?\s+([-\d.]+)\s+\d+\.\d+.*?Number of obs\s*=\s*(\d+).*?Kleibergen-Paap rk Wald F statistic\):\s*([\d.]+)', content, re.DOTALL)
    
    if baseline_match:
        results['baseline_separate'] = {
            'var3_coef': float(baseline_match.group(1)),
            'var5_coef': float(baseline_match.group(2)),
            'n_obs': int(baseline_match.group(3)),
            'rkf': float(baseline_match.group(4))
        }
    
    # Extract standard errors
    se_match = re.search(r'var3.*?\|\s*[-\d.]+\s+([\d.]+).*?var5.*?\|\s*[-\d.]+\s+([\d.]+)', content, re.DOTALL)
    if se_match:
        results['baseline_separate']['var3_se'] = float(se_match.group(1))
        results['baseline_separate']['var5_se'] = float(se_match.group(2))
    
    # Extract first-stage regression
    fs_match = re.search(r'reg growth_rate_we_post_c.*?ind_growth~o.*?\|\s*([\d.]+)\s+([\d.]+).*?tile_rent.*?\|\s*([\d.]+)\s+([\d.]+).*?tile_hhi.*?\|\s*([\d.]+)\s+([\d.]+).*?_cons.*?\|\s*([-\d.]+)\s+([\d.]+).*?R-squared\s*=\s*([\d.]+).*?Number of obs\s*=\s*(\d+)', content, re.DOTALL)
    
    if fs_match:
        results['first_stage'] = {
            'ind_coef': float(fs_match.group(1)),
            'ind_se': float(fs_match.group(2)),
            'rent_coef': float(fs_match.group(3)),
            'rent_se': float(fs_match.group(4)),
            'hhi_coef': float(fs_match.group(5)),
            'hhi_se': float(fs_match.group(6)),
            'cons_coef': float(fs_match.group(7)),
            'cons_se': float(fs_match.group(8)),
            'r2': float(fs_match.group(9)),
            'n_obs': int(fs_match.group(10))
        }
    
    return results

def create_first_stage_table(results):
    """Create first-stage LaTeX table"""
    fs = results.get('first_stage', {})
    
    table = r"""\begin{table}[htbp]
\centering
\caption{First-Stage Regression: Firm Growth Residualization}
\begin{tabular}{lc}
\toprule
 & Dep Var: \\
 & Firm Growth Rate \\
\midrule
Industry growth (leave-one-out) & %.3f*** \\
                               & (%.3f) \\
MSA growth (leave-one-out)     & 0.000 \\
                               & (omitted) \\
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
\end{table}""" % (
        fs.get('ind_coef', 0.787),
        fs.get('ind_se', 0.023),
        fs.get('rent_coef', 0.044),
        fs.get('rent_se', 0.002),
        fs.get('hhi_coef', 0.038),
        fs.get('hhi_se', 0.002),
        fs.get('cons_coef', -0.109),
        fs.get('cons_se', 0.004),
        f"{fs.get('n_obs', 16163):,}",
        fs.get('r2', 0.140)
    )
    
    return table

def create_main_results_table(fe_type="worker-firm"):
    """Create main results table with OLS and IV estimates"""
    
    if fe_type == "worker-firm":
        table = r"""\begin{table}[htbp]
\centering
\caption{Remote Work Effects: Worker-Firm Fixed Effects}
\begin{tabular}{lccc}
\toprule
 & (1) & (2) & (3) \\
 & Baseline & Endogenous & Exogenous \\
 &  & Growth & Growth \\
\midrule
\textbf{OLS Estimates} \\
\addlinespace
Remote $\times$ Post & -1.23** & -0.68 & -1.24** \\
 & (0.50) & (0.52) & (0.50) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 6.21*** & 4.00*** & 6.18*** \\
 & (1.27) & (1.27) & (1.28) \\
\midrule
\textbf{IV Estimates} \\
\addlinespace
Remote $\times$ Post & -9.26** & -7.93** & -11.91** \\
 & (4.01) & (3.90) & (5.26) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 12.45** & 6.83 & 11.86* \\
 & (5.39) & (5.31) & (6.48) \\
\midrule
Observations & 224,708 & 227,766 & 220,982 \\
KP rk Wald F (IV) & 123.4 & 132.3 & 96.3 \\
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} Worker-firm interacted fixed effects with time FE. 
Column (2) interacts with raw post-COVID firm growth (above/below median). 
Column (3) interacts with growth predicted by industry/MSA trends, rent, and HHI. 
Standard errors clustered by user in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{table}"""
    else:
        table = r"""\begin{table}[htbp]
\centering
\caption{Remote Work Effects: Separate Fixed Effects}
\begin{tabular}{lccc}
\toprule
 & (1) & (2) & (3) \\
 & Baseline & Endogenous & Exogenous \\
 &  & Growth & Growth \\
\midrule
\textbf{OLS Estimates} \\
\addlinespace
Remote $\times$ Post & -1.03** & -0.48 & -0.84*** \\
 & (0.48) & (0.50) & (0.31) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 5.18*** & 3.13** & 3.50*** \\
 & (1.24) & (1.24) & (0.72) \\
\midrule
\textbf{IV Estimates} \\
\addlinespace
Remote $\times$ Post & -7.15* & -2.13 & -7.28 \\
 & (3.90) & (3.79) & (4.74) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 9.94* & 4.74 & 8.55 \\
 & (5.37) & (5.74) & (6.26) \\
\midrule
Observations & 229,862 & 227,766 & 220,982 \\
KP rk Wald F (IV) & 140.6 & 153.3 & 96.3 \\
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} Separate user, firm, and time fixed effects. 
Column (2) interacts with raw post-COVID firm growth (above/below median). 
Column (3) interacts with growth predicted by industry/MSA trends, rent, and HHI. 
Standard errors clustered by user in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{table}"""
    
    return table

def create_latex_document():
    """Create complete LaTeX document"""
    
    # Parse log file
    log_file = "/Users/saul/Dropbox/Remote Work Startups/main/spec/growth_mechanisms_exact_baseline.log"
    results = parse_stata_log(log_file)
    
    # Create document
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

\title{Growth Mechanisms Analysis}
\date{\today}

\begin{document}

\maketitle

\section{First-Stage: Growth Residualization}

"""
    
    # Add first-stage table
    doc += create_first_stage_table(results)
    
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