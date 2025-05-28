#!/usr/bin/env python3
"""Build LaTeX tables for the *wage-gap* firm mechanism regressions.

The Stata script `spec/firm_mechanisms_wage_gap.do` produces a CSV with up to
32 specification columns.  This script automatically detects how many
specifications are present, keeps their order, and emits *multiple* LaTeX
tables, each displaying at most 8 columns.  Tables are concatenated into a
single .tex file so the paper can `\input{}` it once.
"""

from pathlib import Path
from textwrap import dedent
import math
import pandas as pd

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPECNAME = "firm_mechanisms_wage_gap"  # must match the new Stata script name
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "firm_mechanisms_wage_gap.tex"

# Maximum columns per table
COLS_PER_TABLE = 8

# Label for parameters
PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Dimension list for check-marks (order matters)
DIMS = ["Rent", "HHI", "Seniority", "sd_wage", "p90_p10_gap"]


# ---------------------------------------------------------------------------
# Helpers
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
        lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.2f})")
    return df


def build_check_matrix(specs: list[str]):
    """Return dict: dim -> list[bool] same length as specs."""
    check = {d: [] for d in DIMS}
    for spec in specs:
        lower = spec.lower()
        check["Rent"].append("rent" in lower)
        check["HHI"].append("hhi" in lower)
        check["Seniority"].append("seniority" in lower)
        check["sd_wage"].append("sd_wage" in lower)
        check["p90_p10_gap"].append("gap" in lower)
    return check


def make_table(df_iv: pd.DataFrame, df_ols: pd.DataFrame, specs: list[str], idx: int) -> list[str]:
    """Return LaTeX lines for one table chunk."""
    check = build_check_matrix(specs)

    # Pivot panels
    def panel_dict(sub):
        return {
            "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
            "se": sub.pivot(index="param", columns="spec", values="se_str"),
        }

    panel = {"A": panel_dict(df_ols[df_ols.spec.isin(specs)]),
             "B": panel_dict(df_iv[df_iv.spec.isin(specs)])}

    # Summary stats
    nobs_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["nobs"].first()
    nobs_ols = df_ols[df_ols.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines: list[str] = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(rf"\caption{{Firm Mechanisms – Wage Dispersion (Part {idx})}}")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    # Group header (growth rate)
    lines.append(r" & \multicolumn{%d}{c}{Growth Rate} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    # Column numbers
    col_nums = " & ".join(f"({i})" for i in range(1, len(specs) + 1))
    lines.append("Specification & " + col_nums + r" \\")
    lines.append(r"\midrule")

    # Check-mark rows
    for dim in DIMS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        pretty = dim.replace("_", " ").title()
        lines.append(pretty + " & " + " & ".join(marks) + r" \\")
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
    lines.append(rf"\label{{tab:firm_mechanisms_wage_gap_{idx}}}")
    lines.append(r"\end{table}")

    return lines


def main() -> None:
    df = load_prepare()
    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    # Keep the order Stata wrote to CSV
    spec_order = df["spec"].drop_duplicates().tolist()

    num_tables = math.ceil(len(spec_order) / COLS_PER_TABLE)
    all_lines: list[str] = []

    for i in range(num_tables):
        chunk = spec_order[i * COLS_PER_TABLE : (i + 1) * COLS_PER_TABLE]
        all_lines.extend(make_table(df_iv, df_ols, chunk, idx=i + 1))
        all_lines.append("")  # blank line between tables

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text("\n".join(all_lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_TEX}")


if __name__ == "__main__":
    main()
