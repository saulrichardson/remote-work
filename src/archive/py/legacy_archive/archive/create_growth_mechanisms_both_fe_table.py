#!/usr/bin/env python3
"""Build LaTeX tables for growth mechanisms analysis with both FE specifications."""

from pathlib import Path
import pandas as pd

# Paths
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[0]

INPUT_CSV = PROJECT_ROOT / "results" / "raw" / "growth_mechanisms_both_fe_precovid" / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "growth_mechanisms_both_fe.tex"

# Load data
df = pd.read_csv(INPUT_CSV)

# Get unique specifications in order
specs = ["baseline", "endo_growth", "exo_growth"]

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

# Create LaTeX table
lines = []
lines.append(r"\begin{table}[htbp]")
lines.append(r"\centering")
lines.append(r"\caption{Remote Work Effects: Comparing Fixed Effects Specifications}")
lines.append(r"\begin{adjustbox}{width=\textwidth}")
lines.append(r"\begin{tabular}{lcccccc}")
lines.append(r"\toprule")
lines.append(r" & \multicolumn{3}{c}{Panel A: Worker-Firm FE} & \multicolumn{3}{c}{Panel B: Separate FE} \\")
lines.append(r"\cmidrule(lr){2-4} \cmidrule(lr){5-7}")
lines.append(r" & (1) & (2) & (3) & (4) & (5) & (6) \\")
lines.append(r" & Baseline & Endogenous & Exogenous & Baseline & Endogenous & Exogenous \\")
lines.append(r" &  & Growth & Growth &  & Growth & Growth \\")
lines.append(r"\midrule")

# Add results for each FE type side by side
for param_name, param_label in [("var3", "Remote $\\times$ Post"), 
                                ("var5", "Remote $\\times$ Post $\\times$ Startup")]:
    
    # Coefficients row
    lines.append(f"{param_label} & ")
    coefs = []
    
    # Worker-Firm FE
    for spec in specs:
        row = df[(df.fe_type == "Worker-Firm FE") & (df.spec == spec) & (df.param == param_name)]
        if len(row) > 0:
            coefs.append(format_coef(row.iloc[0]))
        else:
            coefs.append("-")
    
    # Separate FE
    for spec in specs:
        row = df[(df.fe_type == "Separate FE") & (df.spec == spec) & (df.param == param_name)]
        if len(row) > 0:
            coefs.append(format_coef(row.iloc[0]))
        else:
            coefs.append("-")
    
    lines[-1] += " & ".join(coefs) + r" \\"
    
    # Standard errors row
    lines.append(" & ")
    ses = []
    
    # Worker-Firm FE
    for spec in specs:
        row = df[(df.fe_type == "Worker-Firm FE") & (df.spec == spec) & (df.param == param_name)]
        if len(row) > 0:
            ses.append(f"({row.iloc[0]['se']:.3f})")
        else:
            ses.append("")
    
    # Separate FE
    for spec in specs:
        row = df[(df.fe_type == "Separate FE") & (df.spec == spec) & (df.param == param_name)]
        if len(row) > 0:
            ses.append(f"({row.iloc[0]['se']:.3f})")
        else:
            ses.append("")
    
    lines[-1] += " & ".join(ses) + r" \\"
    
    if param_name == "var3":
        lines.append(r"\addlinespace[0.5em]")

# Add N and F-stat
lines.append(r"\midrule")

# Observations
lines.append("Observations & ")
ns = []

# Worker-Firm FE
for spec in specs:
    row = df[(df.fe_type == "Worker-Firm FE") & (df.spec == spec)]
    if len(row) > 0:
        ns.append(f"{int(row.iloc[0]['nobs']):,}")
    else:
        ns.append("-")

# Separate FE
for spec in specs:
    row = df[(df.fe_type == "Separate FE") & (df.spec == spec)]
    if len(row) > 0:
        ns.append(f"{int(row.iloc[0]['nobs']):,}")
    else:
        ns.append("-")

lines[-1] += " & ".join(ns) + r" \\"

# KP F-stat
lines.append("KP rk Wald F & ")
fs = []

# Worker-Firm FE
for spec in specs:
    row = df[(df.fe_type == "Worker-Firm FE") & (df.spec == spec)]
    if len(row) > 0 and pd.notna(row.iloc[0]['rkf']):
        fs.append(f"{row.iloc[0]['rkf']:.1f}")
    else:
        fs.append("-")

# Separate FE
for spec in specs:
    row = df[(df.fe_type == "Separate FE") & (df.spec == spec)]
    if len(row) > 0 and pd.notna(row.iloc[0]['rkf']):
        fs.append(f"{row.iloc[0]['rkf']:.1f}")
    else:
        fs.append("-")

lines[-1] += " & ".join(fs) + r" \\"

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{adjustbox}")
lines.append(r"\begin{tablenotes}")
lines.append(r"\small")
lines.append(r"\item \textit{Notes:} IV regressions instrumenting remote work with pre-COVID remote policies. ")
lines.append(r"Panel A includes worker-firm fixed effects (firm\_id\#user\_id). ")
lines.append(r"Panel B includes separate firm and user fixed effects. ")
lines.append(r"All specifications include half-year fixed effects. ")
lines.append(r"Standard errors clustered by user in parentheses. ")
lines.append(r"Columns (2) and (5) interact with raw firm growth. ")
lines.append(r"Columns (3) and (6) interact with growth fitted from industry/MSA/rent/HHI. ")
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
for fe_type in ["Worker-Firm FE", "Separate FE"]:
    print(f"\n{fe_type}:")
    for spec_name, spec_label in [("baseline", "Baseline"), 
                                  ("endo_growth", "Endogenous Growth"), 
                                  ("exo_growth", "Exogenous Growth")]:
        data = df[(df.fe_type == fe_type) & (df.spec == spec_name) & (df.param == "var5")]
        if len(data) > 0:
            print(f"  {spec_label} startup effect: {data.iloc[0]['coef']:.3f} ({data.iloc[0]['se']:.3f})")