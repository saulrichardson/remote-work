#!/usr/bin/env python3
r"""Build LaTeX tables for the firm mechanism tests.

The Stata script `spec/firm_mechanisms.do` produces a CSV with up to
32 specification columns (including the wage dimension).  This script
automatically detects how many specifications are present, keeps their order,
and emits *multiple* LaTeX tables, each displaying at most 8 columns.  Tables
are concatenated into a single .tex file so the paper can `\input{}` it once.
"""

from pathlib import Path
from textwrap import dedent
import math
import pandas as pd
import argparse

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

# ---------------------------------------------------------------------------
# CLI arguments (optional mechanism exclusion)
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Create firm mechanisms regression tables")
parser.add_argument(
    "--exclude",
    default="",
    help="Comma-separated list of mechanism dimensions to exclude (e.g. Wage)",
)
args = parser.parse_args()
exclude_set = {x.strip() for x in args.exclude.split(",") if x.strip()}

# Use wage-gap enriched specification results
# Primary specification directory (includes wage dimension by default)
SPECNAME = "firm_mechanisms"
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "firm_mechanisms.tex"

# Maximum columns per table
COLS_PER_TABLE = 8

# Label for parameters
PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Dimension list for check-marks (order matters)
# Optional dimension exclusion via CLI
# Mechanism dimensions (explicit labels preserve capitalisation).
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

# Keywords to detect each mechanism inside spec names
DIM_KEYWORDS = {
    "Rent": ["rent"],
    "HHI": ["hhi"],
    "Seniority": ["seniority"],
    "Wage": ["sd_wage", "sdw", "wage", "gap"],
}

# Apply exclusion list -------------------------------------------------------

if exclude_set:
    DIMS = [d for d in DIMS if d not in exclude_set]
    ROW_LABELS = {k: v for k, v in ROW_LABELS.items() if k in DIMS}


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
            keywords = DIM_KEYWORDS.get(d, [d.lower()])
            check[d].append(any(k in low for k in keywords))
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
    lines.append(rf"\caption{{Firm Mechanisms (Part {idx})}}")
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
        pretty = ROW_LABELS.get(dim, dim)
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
    lines.append(rf"\label{{tab:firm_mechanisms_{idx}}}")
    lines.append(r"\end{table}")

    return lines


def main() -> None:
    df = load_prepare()
    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    # Keep the order Stata wrote to CSV
    spec_all = df["spec"].drop_duplicates().tolist()

    def spec_has_dim(s: str, dim: str) -> bool:
        low = s.lower()
        return any(k in low for k in DIM_KEYWORDS.get(dim, []))

    if exclude_set:
        spec_order = [
            s for s in spec_all if not any(spec_has_dim(s, d) for d in exclude_set)
        ]
        df_iv = df_iv[df_iv.spec.isin(spec_order)]
        df_ols = df_ols[df_ols.spec.isin(spec_order)]
    else:
        spec_order = spec_all

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
