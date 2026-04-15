#!/usr/bin/env python3
"""Build LaTeX table for focused growth mechanisms analysis."""

from pathlib import Path
import pandas as pd

# Paths
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[0]

INPUT_CSV = PROJECT_ROOT / "results" / "raw" / "growth_mechanisms_focused_precovid" / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "growth_mechanisms_focused.tex"

# Load data
df = pd.read_csv(INPUT_CSV)

# Split by model type
df_iv = df[df.model_type == "IV"].copy()
df_ols = df[df.model_type == "OLS"].copy()

# Get unique specifications in order
specs = ["baseline", "endo_growth", "exo_growth"]

# Create LaTeX table
lines = []
lines.append(r"\begin{table}[htbp]")
lines.append(r"\centering")
lines.append(r"\caption{Remote Work Effects: Endogenous vs. Exogenous Growth}")
lines.append(r"\begin{tabular}{lccc}")
lines.append(r"\toprule")

# Header
lines.append(r" & (1) & (2) & (3) \\")
lines.append(r" & Baseline & Endogenous & Exogenous \\")
lines.append(r" &  & Growth & Growth \\")
lines.append(r"\midrule")

# Format coefficient with stars
def format_coef(row):
    p = row['pval']
    stars = ""
    if p < 0.01:
        stars = "***"
    elif p < 0.05:
        stars = "**"
    elif p < 0.1:
        stars = "*"
    return f"{row['coef']:.3f}{stars}"

# Add results for each panel
for panel, model in [("A", "OLS"), ("B", "IV")]:
    lines.append(r"\multicolumn{4}{l}{\textbf{Panel %s: %s}} \\" % (panel, model))
    lines.append(r"\addlinespace")
    
    # Get data for this model
    model_df = df_ols if model == "OLS" else df_iv
    
    # var3 coefficients
    lines.append(r"Remote $\times$ Post & ")
    coefs = []
    for spec in specs:
        row = model_df[(model_df.spec == spec) & (model_df.param == "var3")]
        if len(row) > 0:
            coefs.append(format_coef(row.iloc[0]))
        else:
            coefs.append("-")
    lines[-1] += " & ".join(coefs) + r" \\"
    
    # var3 standard errors
    lines.append(" & ")
    ses = []
    for spec in specs:
        row = model_df[(model_df.spec == spec) & (model_df.param == "var3")]
        if len(row) > 0:
            ses.append(f"({row.iloc[0]['se']:.3f})")
        else:
            ses.append("")
    lines[-1] += " & ".join(ses) + r" \\"
    
    lines.append(r"\addlinespace[0.5em]")
    
    # var5 coefficients
    lines.append(r"Remote $\times$ Post $\times$ Startup & ")
    coefs = []
    for spec in specs:
        row = model_df[(model_df.spec == spec) & (model_df.param == "var5")]
        if len(row) > 0:
            coefs.append(format_coef(row.iloc[0]))
        else:
            coefs.append("-")
    lines[-1] += " & ".join(coefs) + r" \\"
    
    # var5 standard errors
    lines.append(" & ")
    ses = []
    for spec in specs:
        row = model_df[(model_df.spec == spec) & (model_df.param == "var5")]
        if len(row) > 0:
            ses.append(f"({row.iloc[0]['se']:.3f})")
        else:
            ses.append("")
    lines[-1] += " & ".join(ses) + r" \\"
    
    # N and F-stat
    lines.append(r"\midrule")
    
    # Get N for each spec
    lines.append("Observations & ")
    ns = []
    for spec in specs:
        row = model_df[model_df.spec == spec]
        if len(row) > 0:
            ns.append(f"{int(row.iloc[0]['nobs']):,}")
        else:
            ns.append("-")
    lines[-1] += " & ".join(ns) + r" \\"
    
    if model == "IV":
        lines.append("KP rk Wald F & ")
        fs = []
        for spec in specs:
            row = model_df[model_df.spec == spec]
            if len(row) > 0 and pd.notna(row.iloc[0]['rkf']):
                fs.append(f"{row.iloc[0]['rkf']:.2f}")
            else:
                fs.append("-")
        lines[-1] += " & ".join(fs) + r" \\"
    
    if panel == "A":
        lines.append(r"\midrule")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\begin{tablenotes}")
lines.append(r"\small")
lines.append(r"\item \textit{Notes:} All specifications include firm×user and time fixed effects. ")
lines.append(r"Standard errors clustered by user in parentheses. ")
lines.append(r"Column (2) interacts remote work with raw post-COVID firm growth (above/below median). ")
lines.append(r"Column (3) interacts with growth residualized on rent, HHI, industry, and MSA growth. ")
lines.append(r"The coefficients show effects for firms with below-median growth; high-growth firms would add the interaction terms (not shown for brevity). ")
lines.append(r"* p$<$0.10, ** p$<$0.05, *** p$<$0.01.")
lines.append(r"\end{tablenotes}")
lines.append(r"\end{table}")

# Save table
OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_TEX, 'w') as f:
    f.write('\n'.join(lines))

print(f"LaTeX table written to: {OUTPUT_TEX}")

# Print summary
print("\n=== Summary of Results ===")
for spec_name, spec_label in [("baseline", "Baseline"), ("endo_growth", "Endogenous Growth"), ("exo_growth", "Exogenous Growth")]:
    iv_data = df_iv[(df_iv.spec == spec_name) & (df_iv.param == "var5")]
    if len(iv_data) > 0:
        print(f"{spec_label} startup effect (IV): {iv_data.iloc[0]['coef']:.3f} ({iv_data.iloc[0]['se']:.3f})")