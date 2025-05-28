#!/usr/bin/env python3
from pathlib import Path
import pandas as pd

# -----------------------------------------------------------------------------
# 1) Figure out where this script lives & set project root
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

# -----------------------------------------------------------------------------
# 2) Define spec name & paths
# -----------------------------------------------------------------------------
SPECNAME   = "user_mechanisms"
INPUT_CSV  = PROJECT_ROOT / "results" / "raw" / SPECNAME / f"consolidated_results.csv"
# Save final table directly under cleaned folder
OUTPUT_TEX  = PROJECT_ROOT / "results" / "cleaned" / "user_mechanisms.tex"


# -----------------------------------------------------------------------------
# 3) Table configuration
# -----------------------------------------------------------------------------
specs = [
    "baseline", "rent", "hhi", "rent_hhi",
    "seniority", "rent_seniority", "hhi_seniority", "rent_hhi_seniority"
]

param_labels = {
    'var3': r'$ \text{Remote} \times \mathds{1}(\text{Post}) $',
    'var5': r'$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $',
}


dimensions = ["Baseline", "Rent", "HHI", "Seniority"]

def starify(p):
    if p < 0.01:   return "***"
    elif p < 0.05: return "**"
    elif p < 0.1:  return "*"
    else:          return ""

# -----------------------------------------------------------------------------
# 4) Load & prepare data
# -----------------------------------------------------------------------------
df = pd.read_csv(INPUT_CSV)

# Format coefficient & SE strings
df["coef_str"] = df.apply(
    lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ["var3","var5"] else f"{r.coef:.0f}",
    axis=1
)
df["se_str"] = df.se.map(lambda s: f"({s:.2f})")

# Split into IV vs OLS
df_iv  = df[df.model_type == "IV"]
df_ols = df[df.model_type == "OLS"]

# Pivot out coef & se for each panel
def panel_dict(subdf):
    return {
        "coef": subdf.pivot(index="param", columns="spec", values="coef_str"),
        "se":   subdf.pivot(index="param", columns="spec", values="se_str")
    }

panel = {"A": panel_dict(df_ols), "B": panel_dict(df_iv)}

# Extract summary stats by spec
nobs_iv  = df_iv.groupby("spec")["nobs"].first()
nobs_ols = df_ols.groupby("spec")["nobs"].first()
rkf_iv   = df_iv.groupby("spec")["rkf"].first()

# Build top check-mark matrix
check = {dim: [] for dim in dimensions}
for spec in specs:
    check["Baseline"].append(True)
    check["Rent"].append("rent" in spec and spec != "baseline")
    check["HHI"].append("hhi" in spec and spec != "baseline")
    check["Seniority"].append("seniority" in spec)

# -----------------------------------------------------------------------------
# 5) Build LaTeX lines
# -----------------------------------------------------------------------------
lines = []
lines.append(r"\begin{table}[H]")
lines.append(r"\centering")
lines.append(r"\caption{User Productivity Mechanisms}")
lines.append(r"\begin{tabular}{l" + "c"*len(specs) + "}")
lines.append(r"\toprule")

# ---------- NEW: group-header row -------------------------------------------
# Insert descriptive group header – clarify percentile‐rank scaling.
lines.append(
    r" & \multicolumn{%d}{c}{Total Contrib. (pct. rk)} \\" % len(specs)
)
# Draw a rule only under the grouped columns (booktabs)
lines.append(
    r"\cmidrule(lr){2-%d}" % (len(specs) + 1)   # columns are 1-indexed in booktabs
)


lines.append(
    "Specification & " +
    " & ".join(f"({i})" for i in range(1, len(specs)+1)) +
    r" \\"
)
lines.append(r"\midrule")

# Top: check-marks
for dim in dimensions:
    marks = ["\\checkmark" if v else "" for v in check[dim]]
    lines.append(dim + " & " + " & ".join(marks) + r" \\")
lines.append(r"\midrule")

# Panels A & B
# Panels A & B  ---------------------------------------------------------------
panels = [("A", "OLS"), ("B", "IV")]

for i, (panel_id, model) in enumerate(panels):
    # heading
    lines.append(
        r"\multicolumn{" + f"{len(specs)+1}" +
        r"}{l}{\textbf{\uline{Panel " + panel_id + ": " + model + r"}}} \\"
    )
    lines.append(r"\addlinespace")

    # coefficients
    for p in ["var3", "var5"]:
        coefs = panel[panel_id]["coef"].loc[p, specs]
        ses   = panel[panel_id]["se"].loc[p, specs]
        lines.append(param_labels[p] + " & " + " & ".join(coefs) + r" \\")
        lines.append(" & " + " & ".join(ses) + r" \\")

    # summary rows
    nobs_vals = [
        f"{int(nobs_ols[spec]):,}" if model == "OLS" else f"{int(nobs_iv[spec]):,}"
        for spec in specs
    ]
    # separate coefficients from summary statistics
    lines.append(r"\midrule")
    lines.append(r"N & " + " & ".join(nobs_vals) + r" \\")

    if model == "IV":                # first-stage F for IV only
        f_vals = [f"{rkf_iv[spec]:.2f}" for spec in specs]
        lines.append(r"KP\,rk Wald F & " + " & ".join(f_vals) + r" \\")

    # insert a rule between panels
    if i < len(panels) - 1:
        lines.append(r"\midrule")


lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\label{tab:user_mechanisms}")
lines.append(r"\end{table}")

# -----------------------------------------------------------------------------
# 6) Write out .tex
# -----------------------------------------------------------------------------
OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_TEX.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")

