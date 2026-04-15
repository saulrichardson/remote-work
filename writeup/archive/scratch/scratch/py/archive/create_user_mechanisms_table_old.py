#!/usr/bin/env python3
# -----------------------------------------------------------------------------
#  DEPRECATED SCRIPT (archived)
# -----------------------------------------------------------------------------
# This script generated the earliest version of the *user* mechanism tables.
# It is retained for historical reference only; the active pipeline uses
# `create_user_mechanisms_table.py` two directories up.  Executing this file
# manually will write a LaTeX file tagged as deprecated so that it cannot
# overwrite the live artefacts.

from pathlib import Path
import pandas as pd

# 1) Paths
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]

SPECNAME = "user_mechanisms_old"
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "user_mechanisms_deprecated.tex"

# 2) Config
specs = [
    "baseline", "rent", "hhi", "rent_hhi",
    "seniority", "rent_seniority", "hhi_seniority", "rent_hhi_seniority",
]

param_labels = {
    "var3": r"$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) $",
    "var5": r"$ \\text{Remote} \\times \\mathds{1}(\\text{Post}) \\times \\text{Startup} $",
}

dimensions = ["Baseline", "Rent", "HHI", "Seniority"]


def starify(p):
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""

# 3) Load
if not INPUT_CSV.exists():
    raise SystemExit("[deprecated] Raw CSV not found – aborting.")

df = pd.read_csv(INPUT_CSV)

df["coef_str"] = df.apply(
    lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
    axis=1,
)
df["se_str"] = df.se.map(lambda s: f"({s:.2f})")

df_iv = df[df.model_type == "IV"]
df_ols = df[df.model_type == "OLS"]


def panel_dict(subdf):
    return {
        "coef": subdf.pivot(index="param", columns="spec", values="coef_str"),
        "se": subdf.pivot(index="param", columns="spec", values="se_str"),
    }

panel = {"A": panel_dict(df_ols), "B": panel_dict(df_iv)}

nobs_iv = df_iv.groupby("spec")["nobs"].first()
nobs_ols = df_ols.groupby("spec")["nobs"].first()
rkf_iv = df_iv.groupby("spec")["rkf"].first()

check = {dim: [] for dim in dimensions}
for spec in specs:
    check["Baseline"].append(True)
    check["Rent"].append("rent" in spec and spec != "baseline")
    check["HHI"].append("hhi" in spec and spec != "baseline")
    check["Seniority"].append("seniority" in spec)

# 4) LaTeX
lines: list[str] = []
lines.append(r"\\begin{table}[H]")
lines.append(r"\\centering")
lines.append(r"\\caption{User Productivity Mechanisms (Deprecated)}")
lines.append(r"\\begin{tabular}{l" + "c" * len(specs) + "}")
lines.append(r"\\toprule")

lines.append(r" & \\multicolumn{%d}{c}{Total Contrib. (pct. rk)} \\" % len(specs))
lines.append(r"\\cmidrule(lr){2-%d}" % (len(specs) + 1))

lines.append("Specification & " + " & ".join(f"({i})" for i in range(1, len(specs) + 1)) + r" \\")
lines.append(r"\\midrule")

for dim in dimensions:
    marks = ["\\checkmark" if v else "" for v in check[dim]]
    lines.append(dim + " & " + " & ".join(marks) + r" \\")
lines.append(r"\\midrule")

panels = [("A", "OLS"), ("B", "IV")]

for i, (panel_id, model) in enumerate(panels):
    lines.append(r"\\multicolumn{" + f"{len(specs) + 1}" + r"}{l}{\\textbf{\\uline{Panel " + panel_id + ": " + model + r"}}} \\")
    lines.append(r"\\addlinespace")

    for p in ("var3", "var5"):
        coefs = panel[panel_id]["coef"].loc[p, specs]
        ses = panel[panel_id]["se"].loc[p, specs]
        lines.append(param_labels[p] + " & " + " & ".join(coefs) + r" \\")
        lines.append(" & " + " & ".join(ses) + r" \\")

    lines.append(r"\\midrule")
    nobs_vals = [f"{int(nobs_ols[s]):,}" if model == "OLS" else f"{int(nobs_iv[s]):,}" for s in specs]
    lines.append(r"N & " + " & ".join(nobs_vals) + r" \\")

    if model == "IV":
        f_vals = [f"{rkf_iv[s]:.2f}" for s in specs]
        lines.append(r"KP\\,rk Wald F & " + " & ".join(f_vals) + r" \\")

    if i < len(panels) - 1:
        lines.append(r"\\midrule")

lines.append(r"\\bottomrule")
lines.append(r"\\end{tabular}")
lines.append(r"\\label{tab:user_mechanisms_deprecated}")
lines.append(r"\\end{table}")

OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_TEX.write_text("\n".join(lines), encoding="utf-8")
print(f"[deprecated] Wrote LaTeX table to {OUTPUT_TEX.resolve()}")
