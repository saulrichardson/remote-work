#!/usr/bin/env python3
"""Build LaTeX tables for the *Lean‐period* firm mechanism regressions.

Replicates the behaviour of `create_firm_mechanisms_table.py` but points to
the results produced by `spec/firm_mechanisms_lean.do`.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPECNAME = "firm_mechanisms_lean"
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "firm_mechanisms_lean.tex"

# Maximum columns per table
COLS_PER_TABLE = 8

# Label for parameters
PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Dimension list for check-marks (order matters)
# Mechanism dimensions (explicit labels to retain capitalisation).
DIMS = [
    "Rent",
    "HHI",
    "Seniority",
    "Wage",
]

ROW_LABELS = {
    "Rent": "Rent",
    "HHI": "HHI",
    "Seniority": "Seniority",
    "Wage": "Wage",
}


# ---------------------------------------------------------------------------
# Helper functions (straight copy from baseline builder)
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
        lower = spec.lower()
        check["Rent"].append("rent" in lower)
        check["HHI"].append("hhi" in lower)
        check["Seniority"].append("seniority" in lower)
        check["Wage"].append(any(k in lower for k in ("sd_wage", "sdw", "wage", "gap")))
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
    lines.append(rf"\caption{{Firm Mechanisms – Lean (Part {idx})}}")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    # Header ----------------------------------------------------------------
    lines.append(r" & \multicolumn{%d}{c}{Growth Rate} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    col_nums = " & ".join(f"({i})" for i in range(1, len(specs) + 1))
    lines.append("Specification & " + col_nums + r" \\")
    lines.append(r"\midrule")

    # Check‐mark rows --------------------------------------------------------
    for dim in DIMS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        pretty_dim = ROW_LABELS.get(dim, dim)
        lines.append(pretty_dim + " & " + " & ".join(marks) + r" \\")
    lines.append(r"\midrule")

    # Panels -----------------------------------------------------------------
    for p_idx, (panel_id, model) in enumerate([("A", "OLS"), ("B", "IV")]):
        lines.append(r"\multicolumn{%d}{l}{\textbf{\uline{Panel %s: %s}}} \\" % (len(specs)+1, panel_id, model))
        lines.append(r"\addlinespace")

        for param in ("var3", "var5"):
            coefs = panel[panel_id]["coef"].loc[param, specs]
            ses = panel[panel_id]["se"].loc[param, specs]
            lines.append(PARAM_LABELS[param] + " & " + " & ".join(coefs) + r" \\")
            lines.append(" & " + " & ".join(ses) + r" \\")

        # Summary rows -------------------------------------------------------
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
    lines.append(rf"\label{{tab:firm_mechanisms_lean_{idx}}}")
    lines.append(r"\end{table}")

    return lines


# ---------------------------------------------------------------------------
# Main entry‐point
# ---------------------------------------------------------------------------


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Expected Stata output {INPUT_CSV} not found. Run spec/firm_mechanisms_lean.do first."
        )

    df = load_prepare()

    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    spec_order = df["spec"].drop_duplicates().tolist()
    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)

    lines: list[str] = []

    for t_idx in range(tables_needed):
        start = t_idx * COLS_PER_TABLE
        end = min((t_idx + 1) * COLS_PER_TABLE, len(spec_order))
        specs = spec_order[start:end]
        lines.extend(make_table(df_iv, df_ols, specs, t_idx + 1))
        lines.append("")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
