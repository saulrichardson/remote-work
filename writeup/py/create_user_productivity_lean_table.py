#!/usr/bin/env python3
"""Generate LaTeX tables for the *Lean‐period* user‐productivity regressions
with a binary Covid treatment (fully remote = 1 vs. hybrid / in-person < 1).

The script mirrors the structure of *create_user_mechanisms_lean_table.py*
but points to the results produced by
`spec/user_productivity_lean_discrete.do`.  Only the Total‐Contribution
percentile‐rank outcome is available, hence each table contains a single
panel of coefficients for that outcome.
"""

from __future__ import annotations

import math
from pathlib import Path
import argparse

import pandas as pd

# ---------------------------------------------------------------------------
# Paths & CLI args
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]


parser = argparse.ArgumentParser(description="Create lean user-productivity tables (discrete treatment)")
parser.add_argument(
    "--variant",
    choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
    default="precovid",
    help="User panel variant (default: %(default)s)",
)
parser.add_argument(
    "--treat",
    choices=["remote", "nonremote"],
    default="remote",
    help="Discrete treatment definition (default: %(default)s)",
)
parser.add_argument(
    "--exclude",
    default="",
    help="Comma-separated list of mechanism dimensions to exclude (e.g. Wage)",
)

args = parser.parse_args()
variant: str = args.variant
treat: str = args.treat
exclude_set = {x.strip() for x in args.exclude.split(",") if x.strip()}


# ---------------------------------------------------------------------------
# Files & constants
# ---------------------------------------------------------------------------

SPECNAME = f"user_productivity_lean_{variant}_{treat}"

RAW_DIR = PROJECT_ROOT / "results" / "raw"
INPUT_CSV = RAW_DIR / SPECNAME / "consolidated_results.csv"

OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"user_productivity_lean_{variant}_{treat}.tex"

LEGACY_TEX = None

# Table layout parameters ----------------------------------------------------
COLS_PER_TABLE = 8  # same as mechanisms tables

TREAT_BASE_LABEL = {
    "remote": r"\text{Fully Remote}",
    "nonremote": r"\text{Hybrid / In-Person}",
}

label_stub = TREAT_BASE_LABEL.get(treat, r"\text{Remote}")
PARAM_LABELS = {
    "var3": fr"$ {label_stub} \times \mathds{{1}}(\text{{Post}}) $",
    "var5": fr"$ {label_stub} \times \mathds{{1}}(\text{{Post}}) \times \text{{Startup}} $",
}

TREAT_DISPLAY = {
    "remote": "Fully Remote",
    "nonremote": "Hybrid / In-Person",
}
CAPTION_TREAT = TREAT_DISPLAY.get(treat, treat)

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

DIM_KEYWORDS = {
    "Rent": ["rent"],
    "HHI": ["hhi"],
    "Seniority": ["seniority"],
    "Wage": ["sd_wage", "sdw", "wage", "gap"],
}

# Apply exclusions to dimension lists
if exclude_set:
    DIMS = [d for d in DIMS if d not in exclude_set]
    ROW_LABELS = {k: v for k, v in ROW_LABELS.items() if k in DIMS}


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


def load_df() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Expected CSV {INPUT_CSV} not found. Run the Stata spec first.")

    df = pd.read_csv(INPUT_CSV)

    # Pretty coefficient & SE strings
    df["coef_str"] = df.apply(
        lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.2f})")
    return df


def build_check(specs: list[str]):
    out = {d: [] for d in DIMS}
    for s in specs:
        low = s.lower()
        out["Rent"].append("rent" in low)
        out["HHI"].append("hhi" in low)
        out["Seniority"].append("seniority" in low)
        if "Wage" in out:
            out["Wage"].append(any(k in low for k in ("sd_wage", "sdw", "wage", "gap")))
    return out


def pivots(sub: pd.DataFrame):
    return {
        "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
        "se": sub.pivot(index="param", columns="spec", values="se_str"),
    }


def make_table(df_iv: pd.DataFrame, df_ols: pd.DataFrame, specs: list[str], idx: int):
    check = build_check(specs)

    p_iv = pivots(df_iv[df_iv.spec.isin(specs)])
    p_ols = pivots(df_ols[df_ols.spec.isin(specs)])

    nobs_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["nobs"].first()
    nobs_ols = df_ols[df_ols.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf_iv = df_iv[df_iv.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines: list[str] = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    cap_variant = variant.capitalize().replace("_", r"\_")
    cap_treat = CAPTION_TREAT.replace("-", r"\-").replace(" ", "~")
    lines.append(rf"\caption{{User Productivity – Lean ({cap_variant}, {cap_treat}) – Part {idx}}}")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    # Header
    lines.append(r" & \multicolumn{%d}{c}{Total Contrib. (pct. rk)} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    lines.append("Specification & " + " & ".join(f"({i})" for i in range(1, len(specs) + 1)) + r" \\")
    lines.append(r"\midrule")

    # Dimension rows
    for dim in DIMS:
        marks = ["\\checkmark" if v else "" for v in check[dim]]
        pretty_dim = ROW_LABELS.get(dim, dim)
        lines.append(pretty_dim + " & " + " & ".join(marks) + r" \\")
    lines.append(r"\midrule")

    # Panels (OLS / IV)
    for p_idx, (panel_id, model, piv) in enumerate([("A", "OLS", p_ols), ("B", "IV", p_iv)]):
        lines.append(r"\multicolumn{%d}{l}{\textbf{\uline{Panel %s: %s}}} \\" % (len(specs)+1, panel_id, model))
        lines.append(r"\addlinespace")

        for param in ("var3", "var5"):
            coefs = piv["coef"].loc[param, specs]
            ses = piv["se"].loc[param, specs]
            lines.append(PARAM_LABELS[param] + " & " + " & ".join(coefs) + r" \\")
            lines.append(" & " + " & ".join(ses) + r" \\")

        lines.append(r"\midrule")
        if model == "OLS":
            nvals = [f"{int(nobs_ols[s]):,}" for s in specs]
        else:
            nvals = [f"{int(nobs_iv[s]):,}" for s in specs]
        lines.append(r"N & " + " & ".join(nvals) + r" \\")
        if model == "IV":
            kvals = [f"{rkf_iv[s]:.2f}" for s in specs]
            lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

        if p_idx == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(rf"\label{{tab:user_productivity_lean_{variant}_{treat}_{idx}}}")
    lines.append(r"\end{table}")
    return lines


def main():
    df = load_df()

    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    spec_all = df["spec"].drop_duplicates().tolist()

    def spec_has_dim(s: str, dim: str) -> bool:
        low = s.lower()
        return any(k in low for k in DIM_KEYWORDS.get(dim, []))

    if exclude_set:
        spec_order = [s for s in spec_all if not any(spec_has_dim(s, d) for d in exclude_set)]
        df_iv = df_iv[df_iv.spec.isin(spec_order)]
        df_ols = df_ols[df_ols.spec.isin(spec_order)]
    else:
        spec_order = spec_all

    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)
    lines: list[str] = []

    for t_idx in range(tables_needed):
        start, end = t_idx * COLS_PER_TABLE, min((t_idx + 1) * COLS_PER_TABLE, len(spec_order))
        specs = spec_order[start:end]
        lines.extend(make_table(df_iv, df_ols, specs, t_idx + 1))
        lines.append("")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    tex = "\n".join(lines)
    OUTPUT_TEX.write_text(tex)

    if LEGACY_TEX is not None:
        LEGACY_TEX.write_text(tex)


if __name__ == "__main__":
    main()
