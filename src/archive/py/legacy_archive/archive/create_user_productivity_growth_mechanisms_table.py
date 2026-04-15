#!/usr/bin/env python3
"""Build LaTeX tables for user productivity growth mechanisms horse race.

Creates tables showing all combinations of growth and firm characteristic
mechanisms affecting remote work productivity.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import argparse


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

# CLI args
parser = argparse.ArgumentParser(description="Create growth mechanisms tables")
parser.add_argument(
    "--panel",
    default="precovid",
    help="Panel variant to use (default: %(default)s)",
)
args = parser.parse_args()
panel = args.panel

SPECNAME = f"user_productivity_growth_mechanisms_lean_{panel}"
INPUT_CSV = PROJECT_ROOT / "results" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"growth_mechanisms_lean_{panel}.tex"

# Maximum columns per table
COLS_PER_TABLE = 8

# Label for parameters
PARAM_LABELS = {
    "var3": r"Remote $\times$ Post",
    "var5": r"Remote $\times$ Post $\times$ Startup",
}

# Mechanism dimensions
DIMS = [
    "Endo Growth",
    "Exo Growth", 
    "Rent",
    "HHI",
]

ROW_LABELS = {
    "Endo Growth": "Endogenous Growth",
    "Exo Growth": "Exogenous Growth",
    "Rent": "High Rent",
    "HHI": "High HHI",
}

# Keywords to identify which mechanisms are in each specification
DIM_KEYWORDS = {
    "Endo Growth": ["endo"],
    "Exo Growth": ["exo"],
    "Rent": ["rent"],
    "HHI": ["hhi"],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def starify(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def load_prepare() -> pd.DataFrame:
    df = pd.read_csv(INPUT_CSV)

    # Pretty strings
    df["coef_str"] = df.apply(
        lambda r: f"{r.coef:.3f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.3f})")
    return df


def build_check_matrix(specs: list[str]):
    check = {d: [] for d in DIMS}
    for spec in specs:
        low = spec.lower()
        for d in DIMS:
            check[d].append(any(k in low for k in DIM_KEYWORDS.get(d, [d.lower()])))
    return check


def make_table(df_iv: pd.DataFrame, df_ols: pd.DataFrame, specs: list[str], idx: int):
    check = build_check_matrix(specs)

    def panel_dict(sub):
        return {
            "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
            "se": sub.pivot(index="param", columns="spec", values="se_str"),
        }

    panel = {"A": panel_dict(df_ols[df_ols.spec.isin(specs)]),
             "B": panel_dict(df_iv[df_iv.spec.isin(specs)])}

    nobs_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["nobs"].first()
    nobs_ols = df_ols[df_ols.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines: list[str] = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(rf"\caption{{Growth Mechanisms Horse Race (Part {idx})}}")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    # Header
    lines.append(r" & \multicolumn{%d}{c}{User Productivity} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    col_nums = " & ".join(f"({i})" for i in range(1, len(specs) + 1))
    lines.append("Specification & " + col_nums + r" \\")
    lines.append(r"\midrule")

    # Check-mark rows
    for dim in DIMS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        pretty_dim = ROW_LABELS.get(dim, dim)
        lines.append(pretty_dim + " & " + " & ".join(marks) + r" \\")
    lines.append(r"\midrule")

    # Panels
    for p_idx, (panel_id, model) in enumerate([("A", "OLS"), ("B", "IV")]):
        lines.append(r"\multicolumn{%d}{l}{\textbf{\uline{Panel %s: %s}}} \\" % (len(specs)+1, panel_id, model))
        lines.append(r"\addlinespace")

        for param in ("var3", "var5"):
            coefs = panel[panel_id]["coef"].loc[param, specs]
            ses = panel[panel_id]["se"].loc[param, specs]
            lines.append(PARAM_LABELS[param] + " & " + " & ".join(coefs) + r" \\")
            lines.append(" & " + " & ".join(ses) + r" \\")

        # Summary rows
        lines.append(r"\midrule")
        nvals = [f"{int(nobs_ols[s]):,}" if model == "OLS" else f"{int(nobs_iv[s]):,}" for s in specs]
        lines.append(r"N & " + " & ".join(nvals) + r" \\")
        if model == "IV":
            kvals = [f"{rkf_iv[s]:.2f}" for s in specs]
            lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

        if p_idx == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    
    # Add notes
    lines.append(r"\begin{tablenotes}")
    lines.append(r"\small")
    lines.append(r"\item \textit{Notes:} All specifications include firm×user and time fixed effects. ")
    lines.append(r"Standard errors clustered by user. ")
    lines.append(r"Checkmarks indicate which interaction terms are included in each specification. ")
    lines.append(r"Endogenous Growth uses raw post-COVID growth; Exogenous Growth is residualized on rent, HHI, industry, and MSA growth. ")
    lines.append(r"High Rent and High HHI indicate above-median values. ")
    lines.append(r"* p$<$0.10, ** p$<$0.05, *** p$<$0.01.")
    lines.append(r"\end{tablenotes}")
    
    lines.append(rf"\label{{tab:growth_mechanisms_{idx}}}")
    lines.append(r"\end{table}")

    return lines


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Expected Stata output {INPUT_CSV} not found. Run spec/user_productivity_growth_mechanisms_lean.do first."
        )

    df = load_prepare()

    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    # Get unique specifications in order
    spec_order = df["spec"].drop_duplicates().tolist()
    
    # Calculate number of tables needed
    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)

    lines: list[str] = []

    for t_idx in range(tables_needed):
        start = t_idx * COLS_PER_TABLE
        end = min((t_idx + 1) * COLS_PER_TABLE, len(spec_order))
        specs = spec_order[start:end]
        lines.extend(make_table(df_iv, df_ols, specs, t_idx + 1))
        lines.append("")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    tex_content = "\n".join(lines)
    OUTPUT_TEX.write_text(tex_content)
    
    print(f"LaTeX table written to: {OUTPUT_TEX}")
    
    # Print summary statistics
    print("\n=== Key Results Summary ===")
    baseline_iv = df_iv[(df_iv.spec == "baseline") & (df_iv.param == "var5")].iloc[0]
    print(f"Baseline startup effect (IV): {baseline_iv.coef:.3f} ({baseline_iv.se:.3f})")
    
    # Find specifications with significant interactions
    sig_specs = []
    for spec in spec_order[1:]:  # Skip baseline
        spec_data = df_iv[(df_iv.spec == spec) & (df_iv.param == "var5")]
        if len(spec_data) > 0:
            if spec_data.iloc[0].pval < 0.10:
                sig_specs.append(spec)
    
    if sig_specs:
        print(f"\nSpecifications with significant startup effects (p<0.10): {', '.join(sig_specs)}")


if __name__ == "__main__":
    main()