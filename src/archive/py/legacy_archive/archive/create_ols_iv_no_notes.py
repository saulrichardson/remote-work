#!/usr/bin/env python3
"""
Create LaTeX table comparing OLS and IV horse race specifications - NO NOTES
"""

import pandas as pd
import numpy as np
import os

# Define paths
results_dir = "../results/raw"
clean_results_dir = "../results/cleaned"

# Create output directory if it doesn't exist
os.makedirs(clean_results_dir, exist_ok=True)

# Read both CSV files
ols_df = pd.read_csv(f"{results_dir}/horse_race_ols_summary.csv")
iv_df = pd.read_csv(f"{results_dir}/horse_race_full_summary.csv")

print("\nOLS Summary:")
print(ols_df)
print("\nIV Summary:")
print(iv_df)

# Function to format coefficient with stars
def format_coef(coef, se, p_val=None):
    """Format coefficient with standard error and significance stars"""
    # Determine significance based on t-stat (rough approximation)
    t_stat = abs(coef / se) if se > 0 else 0
    stars = ""
    if t_stat > 2.58:  # ~1% level
        stars = "***"
    elif t_stat > 1.96:  # ~5% level
        stars = "**"
    elif t_stat > 1.65:  # ~10% level
        stars = "*"
    
    return f"{coef:.3f}{stars}"

# Create LaTeX table
latex_content = r"""\documentclass[11pt]{article}
\usepackage{booktabs}
\usepackage{array}
\usepackage{multirow}
\usepackage{graphicx}
\usepackage[margin=0.5in]{geometry}
\usepackage{adjustbox}

\begin{document}

\begin{table}[htbp]
\centering
\caption{Horse Race: OLS vs IV Estimates}
\label{tab:horse_race_ols_iv}
\adjustbox{width=\textwidth}{
\begin{tabular}{l*{6}{c}}
\toprule
 & (1) & (2) & (3) & (4) & (5) & (6) \\
 & Baseline & Endogenous & Exogenous & Exo+Vac. & Rent & HHI \\
 & & Growth & Growth & & & \\
\midrule
\multicolumn{7}{l}{\textit{Panel A: OLS Estimates}} \\
Remote $\times$ COVID & """

# Add OLS main effects
for i, row in ols_df.iterrows():
    coef = format_coef(row['var3_coef'], row['var3_se'])
    latex_content += f"{coef} & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in ols_df.iterrows():
    latex_content += f"({row['var3_se']:.3f}) & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add Remote × COVID × Startup
latex_content += "Remote $\\times$ COVID $\\times$ Startup & "
for i, row in ols_df.iterrows():
    coef = format_coef(row['var5_coef'], row['var5_se'])
    latex_content += f"{coef} & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in ols_df.iterrows():
    latex_content += f"({row['var5_se']:.3f}) & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add OLS interaction effects
latex_content += "Remote $\\times$ COVID $\\times$ High [Variable] & "
for i, row in ols_df.iterrows():
    if pd.notna(row['var3_int_coef']):
        coef = format_coef(row['var3_int_coef'], row['var3_int_se'])
        latex_content += f"{coef} & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in ols_df.iterrows():
    if pd.notna(row['var3_int_se']):
        latex_content += f"({row['var3_int_se']:.3f}) & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Remote × COVID × Startup × High [Variable]
latex_content += "Remote $\\times$ COVID $\\times$ Startup $\\times$ High [Variable] & "
for i, row in ols_df.iterrows():
    if pd.notna(row['var5_int_coef']):
        coef = format_coef(row['var5_int_coef'], row['var5_int_se'])
        latex_content += f"{coef} & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in ols_df.iterrows():
    if pd.notna(row['var5_int_se']):
        latex_content += f"({row['var5_int_se']:.3f}) & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add separator
latex_content += r"\midrule" + "\n"
latex_content += r"\multicolumn{7}{l}{\textit{Panel B: IV Estimates}} \\" + "\n"

# Add IV main effects
latex_content += "Remote $\\times$ COVID & "
for i, row in iv_df.iterrows():
    coef = format_coef(row['var3_coef'], row['var3_se'])
    latex_content += f"{coef} & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in iv_df.iterrows():
    latex_content += f"({row['var3_se']:.3f}) & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add Remote × COVID × Startup
latex_content += "Remote $\\times$ COVID $\\times$ Startup & "
for i, row in iv_df.iterrows():
    coef = format_coef(row['var5_coef'], row['var5_se'])
    latex_content += f"{coef} & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in iv_df.iterrows():
    latex_content += f"({row['var5_se']:.3f}) & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add IV interaction effects
latex_content += "Remote $\\times$ COVID $\\times$ High [Variable] & "
for i, row in iv_df.iterrows():
    if pd.notna(row['var3_int_coef']):
        coef = format_coef(row['var3_int_coef'], row['var3_int_se'])
        latex_content += f"{coef} & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in iv_df.iterrows():
    if pd.notna(row['var3_int_se']):
        latex_content += f"({row['var3_int_se']:.3f}) & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Remote × COVID × Startup × High [Variable]
latex_content += "Remote $\\times$ COVID $\\times$ Startup $\\times$ High [Variable] & "
for i, row in iv_df.iterrows():
    if pd.notna(row['var5_int_coef']):
        coef = format_coef(row['var5_int_coef'], row['var5_int_se'])
        latex_content += f"{coef} & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add standard errors
latex_content += " & "
for i, row in iv_df.iterrows():
    if pd.notna(row['var5_int_se']):
        latex_content += f"({row['var5_int_se']:.3f}) & "
    else:
        latex_content += " & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# Add observations
latex_content += r"\midrule" + "\n"
latex_content += "Observations & "
for i, row in ols_df.iterrows():
    latex_content += f"{row['N']:,} & "
latex_content = latex_content[:-2] + r" \\" + "\n"

# End table WITHOUT NOTES
latex_content += r"""\bottomrule
\end{tabular}
}
\end{table}

\end{document}
"""

# Write LaTeX file
output_file = f"{clean_results_dir}/horse_race_ols_iv_no_notes.tex"
with open(output_file, 'w') as f:
    f.write(latex_content)

print(f"\nLaTeX table written to: {output_file}")

# Also create a standalone table version
standalone_content = latex_content.split(r"\begin{tabular}")[1].split(r"\end{document}")[0]
standalone_content = r"\begin{tabular}" + standalone_content

standalone_file = f"{clean_results_dir}/horse_race_ols_iv_no_notes_standalone.tex"
with open(standalone_file, 'w') as f:
    f.write(standalone_content)

print(f"Standalone table written to: {standalone_file}")

# Print key comparisons
print("\n=== KEY OLS vs IV COMPARISONS ===")
print("\nBaseline startup effect:")
print(f"  OLS:  {ols_df.loc[0, 'var5_coef']:.3f} pp")
print(f"  IV:   {iv_df.loc[0, 'var5_coef']:.3f} pp")
print(f"  Difference: {iv_df.loc[0, 'var5_coef'] - ols_df.loc[0, 'var5_coef']:.3f} pp")

print("\nEndogenous growth - Low-growth startup effect:")
print(f"  OLS:  {ols_df.loc[1, 'var5_coef']:.3f} pp")
print(f"  IV:   {iv_df.loc[1, 'var5_coef']:.3f} pp")
print(f"  Difference: {iv_df.loc[1, 'var5_coef'] - ols_df.loc[1, 'var5_coef']:.3f} pp")

print("\nEndogenous growth - High-growth differential:")
print(f"  OLS:  {ols_df.loc[1, 'var5_int_coef']:.3f} pp")
print(f"  IV:   {iv_df.loc[1, 'var5_int_coef']:.3f} pp")