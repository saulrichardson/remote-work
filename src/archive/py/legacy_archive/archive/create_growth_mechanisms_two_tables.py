#!/usr/bin/env python3
"""Build two separate tables for growth mechanisms analysis - one for each FE specification."""

from pathlib import Path
import pandas as pd

# Paths
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[0]

INPUT_CSV = PROJECT_ROOT / "results" / "raw" / "growth_mechanisms_both_fe_precovid" / "consolidated_results.csv"
OUTPUT_TEX1 = PROJECT_ROOT / "results" / "cleaned" / "growth_mechanisms_worker_firm_fe.tex"
OUTPUT_TEX2 = PROJECT_ROOT / "results" / "cleaned" / "growth_mechanisms_separate_fe.tex"

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

def create_table(fe_type, title, output_path):
    """Create a table for a specific FE type."""
    lines = []
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"\centering")
    lines.append(f"\\caption{{{title}}}")
    lines.append(r"\begin{tabular}{lccc}")
    lines.append(r"\toprule")
    
    # Header
    lines.append(r" & (1) & (2) & (3) \\")
    lines.append(r" & Baseline & Endogenous & Exogenous \\")
    lines.append(r" &  & Growth & Growth \\")
    lines.append(r"\midrule")
    
    # IV results only
    lines.append(r"\textbf{IV Estimates} \\")
    lines.append(r"\addlinespace")
    
    # var3 coefficients
    lines.append(r"Remote $\times$ Post & ")
    coefs = []
    for spec in specs:
        row = df[(df.fe_type == fe_type) & (df.spec == spec) & (df.param == "var3")]
        if len(row) > 0:
            coefs.append(format_coef(row.iloc[0]))
        else:
            coefs.append("-")
    lines[-1] += " & ".join(coefs) + r" \\"
    
    # var3 standard errors
    lines.append(" & ")
    ses = []
    for spec in specs:
        row = df[(df.fe_type == fe_type) & (df.spec == spec) & (df.param == "var3")]
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
        row = df[(df.fe_type == fe_type) & (df.spec == spec) & (df.param == "var5")]
        if len(row) > 0:
            coefs.append(format_coef(row.iloc[0]))
        else:
            coefs.append("-")
    lines[-1] += " & ".join(coefs) + r" \\"
    
    # var5 standard errors
    lines.append(" & ")
    ses = []
    for spec in specs:
        row = df[(df.fe_type == fe_type) & (df.spec == spec) & (df.param == "var5")]
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
        row = df[(df.fe_type == fe_type) & (df.spec == spec)]
        if len(row) > 0:
            ns.append(f"{int(row.iloc[0]['nobs']):,}")
        else:
            ns.append("-")
    lines[-1] += " & ".join(ns) + r" \\"
    
    lines.append("KP rk Wald F & ")
    fs = []
    for spec in specs:
        row = df[(df.fe_type == fe_type) & (df.spec == spec)]
        if len(row) > 0 and pd.notna(row.iloc[0]['rkf']):
            fs.append(f"{row.iloc[0]['rkf']:.1f}")
        else:
            fs.append("-")
    lines[-1] += " & ".join(fs) + r" \\"
    
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\begin{tablenotes}")
    lines.append(r"\small")
    lines.append(r"\item \textit{Notes:} IV regressions instrumenting remote work with pre-COVID remote policies. ")
    if "Worker-Firm" in fe_type:
        lines.append(r"Fixed effects include worker-firm pairs (firm\_id\#user\_id) and half-years. ")
    else:
        lines.append(r"Fixed effects include separate firm, user, and half-year effects. ")
    lines.append(r"Standard errors clustered by user in parentheses. ")
    lines.append(r"Column (2) interacts remote work with raw post-COVID firm growth (above/below median). ")
    lines.append(r"Column (3) interacts with growth predicted by industry/MSA trends, rent, and HHI. ")
    lines.append(r"* p$<$0.10, ** p$<$0.05, *** p$<$0.01.")
    lines.append(r"\end{tablenotes}")
    lines.append(r"\end{table}")
    
    # Save table
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"LaTeX table written to: {output_path}")

# Create both tables
create_table("Worker-Firm FE", 
             "Remote Work Effects: Worker-Firm Fixed Effects",
             OUTPUT_TEX1)

create_table("Separate FE", 
             "Remote Work Effects: Separate Firm and User Fixed Effects",
             OUTPUT_TEX2)

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