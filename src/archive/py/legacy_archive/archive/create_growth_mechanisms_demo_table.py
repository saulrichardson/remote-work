#!/usr/bin/env python3
"""Build LaTeX table for growth mechanisms demo."""

from pathlib import Path
import pandas as pd

# Paths
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[0]

INPUT_CSV = PROJECT_ROOT / "results" / "raw" / "growth_mechanisms_demo_precovid" / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "growth_mechanisms_demo.tex"

# Load data
df = pd.read_csv(INPUT_CSV)

# Split by model type
df_iv = df[df.model_type == "IV"].copy()
df_ols = df[df.model_type == "OLS"].copy()

# Get unique specifications
specs = df["spec"].drop_duplicates().tolist()

# Create LaTeX table
lines = []
lines.append(r"\begin{table}[htbp]")
lines.append(r"\centering")
lines.append(r"\caption{Growth Mechanisms Horse Race - Key Specifications}")
lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
lines.append(r"\toprule")

# Header
col_labels = {
    "baseline": "(1)\nBaseline",
    "growth": "(2)\nGrowth",
    "rent": "(3)\nRent",
    "hhi": "(4)\nHHI",
    "growth_rent_hhi": "(5)\nAll"
}
header = " & ".join([col_labels.get(s, s) for s in specs])
lines.append(" & " + header + r" \\")
lines.append(r"\midrule")

# Checkmarks for mechanisms
mechanisms = {
    "Growth": ["growth", "growth_rent_hhi"],
    "High Rent": ["rent", "growth_rent_hhi"],  
    "High HHI": ["hhi", "growth_rent_hhi"]
}

for mech, includes in mechanisms.items():
    row = [mech]
    for spec in specs:
        if spec in includes:
            row.append(r"\checkmark")
        else:
            row.append("")
    lines.append(" & ".join(row) + r" \\")

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
    lines.append(r"\multicolumn{%d}{l}{\textbf{Panel %s: %s}} \\" % (len(specs)+1, panel, model))
    
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
    lines.append("N & ")
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
lines.append(r"Standard errors clustered by user. Checkmarks indicate which interaction terms are included. ")
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
iv_baseline = df_iv[(df_iv.spec == "baseline") & (df_iv.param == "var5")].iloc[0]
print(f"Baseline startup effect (IV): {iv_baseline['coef']:.3f} ({iv_baseline['se']:.3f})")

for spec in ["growth", "rent", "hhi"]:
    spec_data = df_iv[(df_iv.spec == spec) & (df_iv.param == "var5")]
    if len(spec_data) > 0:
        print(f"{spec.capitalize()} startup effect (IV): {spec_data.iloc[0]['coef']:.3f} ({spec_data.iloc[0]['se']:.3f})")