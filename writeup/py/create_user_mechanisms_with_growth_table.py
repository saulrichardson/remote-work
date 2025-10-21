#!/usr/bin/env python3
"""
Create LaTeX tables for the combined user mechanisms + growth specs.

This mirrors writeup/py/create_user_mechanisms_table.py but reads
results from the new Stata driver spec/user_mechanisms_with_growth.do
and inserts two growth columns (endogenous, exogenous) alongside the
standard mechanism columns. Output keeps a Panel A (OLS) / Panel B (IV)
layout and splits into chunks of up to 8 columns per table.
"""
from __future__ import annotations

from pathlib import Path
import math
import argparse
import pandas as pd


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

DEFAULT_VARIANT = "precovid"

parser = argparse.ArgumentParser(description="Create user mechanisms + growth latex table")
parser.add_argument(
    "--variant",
    choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
    default=DEFAULT_VARIANT,
    help="Which user_panel sample variant to load (default: %(default)s)",
)
args = parser.parse_args()

variant = args.variant

# Input/Output paths ---------------------------------------------------------
RAW_DIR = PROJECT_ROOT / "results" / "raw"
SPECNAME = f"user_mechanisms_with_growth_{variant}"
INPUT_CSV = RAW_DIR / SPECNAME / "consolidated_results.csv"

OUTPUT_DIR = PROJECT_ROOT / "results" / "cleaned"
OUTPUT_TEX_BASE = OUTPUT_DIR / f"user_mechanisms_with_growth_{variant}.tex"
OUTPUT_TEX_OLS  = OUTPUT_DIR / f"user_mechanisms_with_growth_{variant}_ols.tex"
OUTPUT_TEX_IV   = OUTPUT_DIR / f"user_mechanisms_with_growth_{variant}_iv.tex"


# Display settings -----------------------------------------------------------
COLS_PER_TABLE = 12

PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Dimension checklist rows (growth rows listed last to match column layout).
DIMS = [
    "rent",
    "hhi",
    "seniority",
    "growth_endog",
]

ROW_LABELS = {
    "rent": "Rent",
    "hhi": "HHI",
    "seniority": "Seniority",
    "growth_endog": "Post-COVID Growth",
}

DIM_KEYWORDS = {
    "rent": ["rent"],
    "hhi": ["hhi"],
    "seniority": ["seniority"],
    "growth_endog": ["growth_endog"],
}


def starify(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def load_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Expect columns: model_type, spec, param, coef, se, pval, rkf, nobs
    df["coef_str"] = df.apply(
        lambda r: f"{r.coef:.2f}{starify(r.pval)}" if r.param in ("var3", "var5") else f"{r.coef:.0f}",
        axis=1,
    )
    df["se_str"] = df.se.map(lambda s: f"({s:.2f})")
    return df


def spec_has_dim(spec: str, dim: str) -> bool:
    low = spec.lower()
    return any(token in low for token in DIM_KEYWORDS.get(dim, []))


def checks(specs: list[str]) -> dict[str, list[bool]]:
    flags: dict[str, list[bool]] = {dim: [] for dim in DIMS}
    for spec in specs:
        for dim in DIMS:
            flags[dim].append(spec_has_dim(spec, dim))
    return flags


def panel(sub: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "coef": sub.pivot(index="param", columns="spec", values="coef_str"),
        "se": sub.pivot(index="param", columns="spec", values="se_str"),
    }


def format_table_chunk_for_model(
    df_model: pd.DataFrame,
    model_name: str,
    specs: list[str],
    idx: int,
    total_parts: int,
) -> list[str]:
    checkmarks = checks(specs)
    pdata = panel(df_model[df_model.spec.isin(specs)])

    nobs = df_model[df_model.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf = None
    if model_name == "IV" and "rkf" in df_model.columns:
        rkf = df_model[df_model.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines: list[str] = []
    lines.append(
        f"% Auto-generated block: {model_name} (part {idx} of {total_parts})"
    )
    lines.append(r"{\centering")
    lines.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    lines.append(r"\toprule")

    lines.append(r" & \multicolumn{%d}{c}{Contributions} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    lines.append(" & " + " & ".join(f"({i})" for i in range(1, len(specs) + 1)) + r" \\")
    lines.append(r"\midrule")

    for param in ("var3", "var5"):
        coefs = pdata["coef"].loc[param, specs]
        ses = pdata["se"].loc[param, specs]
        lines.append(PARAM_LABELS[param] + " & " + " & ".join(coefs) + r" \\")
        lines.append(" & " + " & ".join(ses) + r" \\")

    # Separator between coefficients and Fixed Effects/Controls blocks
    lines.append(r"\midrule")

    # Fixed Effects header and rows
    header_blanks = " & ".join([""] * len(specs))
    lines.append(r"\textbf{Fixed Effects} & " + header_blanks + r" \\")

    ck = " & ".join([r"$\checkmark$"] * len(specs))
    INDENT = r"\hspace{1em}"
    lines.append(INDENT + r"Time FE & " + ck + r" \\")
    lines.append(INDENT + r"Firm $\times$ User FE & " + ck + r" \\")

    # Controls header and dimension checklist rows
    lines.append(r"\midrule")
    lines.append(r"\textbf{Controls} & " + header_blanks + r" \\")
    for dim in DIMS:
        marks = ['\\checkmark' if flag else '' for flag in checkmarks[dim]]
        row = [INDENT + ROW_LABELS[dim]] + marks
        lines.append(' & '.join(row) + r' \\')
    lines.append(r"\midrule")

    # Sample size and first-stage strength rows at the bottom
    nvals = [f"{int(nobs[s]):,}" for s in specs]
    lines.append(r"N & " + " & ".join(nvals) + r" \\")
    if model_name == "IV" and rkf is not None:
        kvals = [f"{rkf[s]:.2f}" for s in specs]
        lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"}")
    return lines


def main():
    if not INPUT_CSV.exists():
        raise SystemExit(f"Missing input CSV: {INPUT_CSV}")

    df = load_df(INPUT_CSV)
    df_iv = df[df.model_type == "IV"].copy()
    df_ols = df[df.model_type == "OLS"].copy()

    all_specs = df["spec"].drop_duplicates().tolist()
    baseline = [s for s in all_specs if s == "baseline"]
    growth = [s for s in ["growth_endog"] if s in all_specs]
    excluded = set(baseline + growth + ["growth_exog"])
    middle = [s for s in all_specs if s not in excluded]
    # Drop pairwise mechanism combinations (columns 5–7 in prior layout)
    drop_pairs = {"rent_hhi", "rent_seniority", "hhi_seniority"}
    middle = [s for s in middle if s not in drop_pairs]
    spec_order = baseline + middle + growth

    tables_needed = math.ceil(len(spec_order) / COLS_PER_TABLE)
    lines_ols: list[str] = []
    lines_iv: list[str] = []
    for i in range(tables_needed):
        chunk = spec_order[i * COLS_PER_TABLE : (i + 1) * COLS_PER_TABLE]
        lines_ols.extend(
            format_table_chunk_for_model(
                df_ols,
                "OLS",
                chunk,
                idx=i + 1,
                total_parts=tables_needed,
            )
        )
        lines_ols.append("")

        lines_iv.extend(
            format_table_chunk_for_model(
                df_iv,
                "IV",
                chunk,
                idx=i + 1,
                total_parts=tables_needed,
            )
        )
        lines_iv.append("")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX_OLS.write_text("\n".join(lines_ols), encoding="utf-8")
    OUTPUT_TEX_IV.write_text("\n".join(lines_iv), encoding="utf-8")
    # Remove legacy combined file if it exists to avoid confusion
    if OUTPUT_TEX_BASE.exists():
        try:
            OUTPUT_TEX_BASE.unlink()
        except OSError:
            pass
    print(f"Wrote {OUTPUT_TEX_OLS}")
    print(f"Wrote {OUTPUT_TEX_IV}")


if __name__ == "__main__":
    main()
