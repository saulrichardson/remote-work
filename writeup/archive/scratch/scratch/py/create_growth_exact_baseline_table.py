#!/usr/bin/env python3
"""
Create LaTeX table from exact baseline growth mechanisms results
"""

import pandas as pd
import numpy as np
import os

# Define paths
results_dir = "../../results/raw"
output_dir = "../../results/cleaned"

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Manually create the results table based on the log file
# These are the exact results from growth_mechanisms_exact_baseline.log

results = {
    'Baseline (All Obs)': {
        'var3_coef': -7.151,
        'var3_se': 3.899,
        'var5_coef': 9.937,
        'var5_se': 5.371,
        'N': 229862,
        'rkf': 140.6,
        'fe': 'Separate FE'
    },
    'Baseline (All Obs, Firm×User)': {
        'var3_coef': -9.263,
        'var3_se': 4.014,
        'var5_coef': 12.453,
        'var5_se': 5.393,
        'N': 224708,
        'rkf': 123.4,
        'fe': 'Firm×User FE'
    }
}

# Create LaTeX table
def create_latex_table():
    latex = r"""\begin{table}[htbp]
\centering
\caption{Exact Baseline Replication: Matching Mini-Report}
\begin{tabular}{lcc}
\toprule
 & (1) & (2) \\
 & Mini-Report & Growth Analysis \\
 & Baseline & (All Obs) \\
\midrule
\textbf{Panel A: Separate Fixed Effects} \\
\addlinespace
Remote $\times$ Post & -7.15* & -7.15* \\
 & (3.90) & (3.90) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 9.94* & 9.94* \\
 & (5.37) & (5.37) \\
\addlinespace
Observations & 229,862 & 229,862 \\
KP rk Wald F & 140.6 & 140.6 \\
\midrule
\textbf{Panel B: Worker-Firm Fixed Effects} \\
\addlinespace
Remote $\times$ Post & -- & -9.26** \\
 &  & (4.01) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & -- & 12.45** \\
 &  & (5.39) \\
\addlinespace
Observations & -- & 224,708 \\
KP rk Wald F & -- & 123.4 \\
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} Column (1) shows results from mini-report.pdf Table 3. 
Column (2) shows our exact replication using relaxed merge to preserve all observations.
Panel A uses separate user, firm, and time fixed effects. 
Panel B uses worker-firm interacted fixed effects (more restrictive).
Standard errors clustered by user in parentheses. 
* p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{table}"""
    
    return latex

# Also create growth results table
def create_growth_table():
    latex = r"""\begin{table}[htbp]
\centering
\caption{Growth Mechanisms Analysis (Subset with Controls)}
\begin{tabular}{lccc}
\toprule
 & (1) & (2) & (3) \\
 & Baseline & Endogenous & Exogenous \\
 & (Subset) & Growth & Growth \\
\midrule
\textbf{Panel A: Separate Fixed Effects} \\
\addlinespace
Remote $\times$ Post & -7.17* & -2.13 & -7.28 \\
 & (3.91) & (3.79) & (4.74) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 9.86* & 4.74 & 8.55 \\
 & (5.45) & (5.74) & (6.26) \\
\addlinespace
Observations & 227,766 & 227,766 & 220,982 \\
\midrule
\textbf{Panel B: Worker-Firm Fixed Effects} \\
\addlinespace
Remote $\times$ Post & -9.27** & -7.93** & -11.91** \\
 & (4.02) & (3.90) & (5.26) \\
\addlinespace[0.5em]
Remote $\times$ Post $\times$ Startup & 12.33** & 6.83 & 11.86* \\
 & (5.39) & (5.31) & (6.48) \\
\addlinespace
Observations & 227,766 & 227,766 & 220,982 \\
\bottomrule
\end{tabular}
\begin{tablenotes}
\small
\item \textit{Notes:} This table uses only the subset of observations with rent/HHI controls needed for growth residualization.
Column (2) interacts with raw firm growth. Column (3) interacts with growth predicted by industry/MSA/rent/HHI.
Standard errors clustered by user. * p$<$0.10, ** p$<$0.05, *** p$<$0.01.
\end{tablenotes}
\end{table}"""
    
    return latex

# Save tables
with open(os.path.join(output_dir, "exact_baseline_comparison.tex"), "w") as f:
    f.write(create_latex_table())

with open(os.path.join(output_dir, "growth_mechanisms_updated.tex"), "w") as f:
    f.write(create_growth_table())

print("Tables created successfully!")
print(f"Saved to: {output_dir}/exact_baseline_comparison.tex")
print(f"Saved to: {output_dir}/growth_mechanisms_updated.tex")