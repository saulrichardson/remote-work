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

import sys
from pathlib import Path
import math
import argparse
import pandas as pd


HERE = Path(__file__).resolve().parent
PY_DIR = HERE.parents[1] / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_FINAL_TEX, RESULTS_RAW

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
RAW_DIR = RESULTS_RAW
SPECNAME = f"user_mechanisms_with_growth_{variant}"
INPUT_CSV = RAW_DIR / SPECNAME / "consolidated_results.csv"

OUTPUT_DIR = RESULTS_FINAL_TEX
OUTPUT_TEX_BASE = OUTPUT_DIR / f"user_mechanisms_with_growth_{variant}.tex"
OUTPUT_TEX_OLS  = OUTPUT_DIR / f"user_mechanisms_with_growth_{variant}_ols.tex"
OUTPUT_TEX_IV   = OUTPUT_DIR / f"user_mechanisms_with_growth_{variant}_iv.tex"


# Display settings -----------------------------------------------------------
COLS_PER_TABLE = 12

PARAM_LABELS = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}
PARAM_ORDER = ["var3", "var5"]
INDENT = r"\hspace{1em}"


def _tabular_star_spec(n_cols: int) -> str:
    return "@{}l" + "@{\\extracolsep{\\fill}}c" * n_cols + "@{}"

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


def fmt_cell(coef: float, se: float, pval: float) -> str:
    """Return centred coefficient/SE stack following the standard layout."""
    return r"\makecell[c]{{{coef:.2f}{stars}\\({se:.2f})}}".format(
        coef=coef,
        stars=starify(pval),
        se=se,
    )


def load_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
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



def format_table_chunk_for_model(
    df_model: pd.DataFrame,
    model_name: str,
    specs: list[str],
    idx: int,
    total_parts: int,
) -> list[str]:
    checkmarks = checks(specs)
    nobs = df_model[df_model.spec.isin(specs)].groupby("spec")["nobs"].first()
    rkf = None
    if model_name == "IV" and "rkf" in df_model.columns:
        rkf = df_model[df_model.spec.isin(specs)].groupby("spec")["rkf"].first()

    lines: list[str] = []
    lines.append(
        f"% Auto-generated block: {model_name} (part {idx} of {total_parts})"
    )
    col_spec = _tabular_star_spec(len(specs))
    lines.append(r"{\centering")
    lines.append(rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}")
    lines.append(r"\toprule")

    lines.append(r" & \multicolumn{%d}{c}{Contributions} \\" % len(specs))
    lines.append(r"\cmidrule(lr){2-%d}" % (len(specs) + 1))

    lines.append(" & " + " & ".join(f"({i})" for i in range(1, len(specs) + 1)) + r" \\")
    lines.append(r"\midrule")

    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABELS[param]]
        for spec in specs:
            entry = df_model[(df_model["spec"] == spec) & (df_model["param"] == param)].head(1)
            if entry.empty:
                row.append("")
            else:
                coef = float(entry.iloc[0]["coef"])
                se = float(entry.iloc[0]["se"])
                pval = float(entry.iloc[0]["pval"])
                row.append(fmt_cell(coef, se, pval))
        lines.append(" & ".join(row) + r" \\")

    # Separator between coefficients and Fixed Effects/Controls blocks
    lines.append(r"\midrule")

    # Fixed Effects header and rows
    header_blanks = " & ".join([""] * len(specs))
    lines.append(r"\textbf{Fixed Effects} & " + header_blanks + r" \\")

    ck = " & ".join([r"$\checkmark$"] * len(specs))
    lines.append(INDENT + r"Time & " + ck + r" \\")
    lines.append(INDENT + r"Firm $\times$ Individual & " + ck + r" \\")

    # Controls header and dimension checklist rows
    lines.append(r"\midrule")
    lines.append(r"\textbf{Controls} & " + header_blanks + r" \\")
    for dim in DIMS:
        marks = ["\\checkmark" if flag else "" for flag in checkmarks[dim]]
        row = [INDENT + ROW_LABELS[dim]] + marks
        lines.append(" & ".join(row) + r" \\")
    lines.append(r"\midrule")

    # Sample size and first-stage strength rows at the bottom
    nvals = [f"{int(nobs[s]):,}" for s in specs]
    lines.append(r"N & " + " & ".join(nvals) + r" \\")
    if model_name == "IV" and rkf is not None:
        kvals = [f"{rkf[s]:.2f}" for s in specs]
        lines.append(r"KP\,rk Wald F & " + " & ".join(kvals) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    lines.append(r"}")
    return lines


def panel_block(
    df_model: pd.DataFrame,
    specs: list[str],
) -> list[str]:
    lines: list[str] = []
    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABELS[param]]
        for spec in specs:
            entry = df_model[(df_model["spec"] == spec) & (df_model["param"] == param)].head(1)
            if entry.empty:
                row.append("")
            else:
                coef = float(entry.iloc[0]["coef"])
                se = float(entry.iloc[0]["se"])
                pval = float(entry.iloc[0]["pval"])
                row.append(fmt_cell(coef, se, pval))
        lines.append(" & ".join(row) + r" \\")
    return lines


def fixed_effects_block(num_cols: int) -> list[str]:
    blanks = " & ".join([""] * num_cols)
    checks = " & ".join([r"$\checkmark$"] * num_cols)
    return [
        r"\textbf{Fixed Effects} & " + blanks + r" \\",
        INDENT + r"Time & " + checks + r" \\",
        INDENT + r"Firm $\times$ Individual & " + checks + r" \\",
    ]


def controls_block(specs: list[str]) -> list[str]:
    marks = checks(specs)
    blanks = " & ".join([""] * len(specs))
    lines = [r"\textbf{Controls} & " + blanks + r" \\"]
    for dim in DIMS:
        row_marks = ["\\checkmark" if flag else "" for flag in marks[dim]]
        lines.append(INDENT + ROW_LABELS[dim] + " & " + " & ".join(row_marks) + r" \\")
    return lines


def panel_stats_block(df_model: pd.DataFrame, specs: list[str], *, model: str) -> list[str]:
    """Return per-panel summary stats (N, KP rk Wald F for IV)."""
    lines: list[str] = []

    n_values: list[str] = []
    for spec in specs:
        sub = df_model[df_model["spec"] == spec]
        if sub.empty or pd.isna(sub.iloc[0]["nobs"]):
            n_values.append("")
        else:
            n_values.append(f"{int(sub.iloc[0]['nobs']):,}")
    lines.append("N & " + " & ".join(n_values) + r" \\")

    if model == "IV" and "rkf" in df_model.columns:
        rkf_values: list[str] = []
        for spec in specs:
            sub = df_model[df_model["spec"] == spec]
            if sub.empty:
                rkf_values.append("")
                continue
            val = sub.iloc[0].get("rkf", float("nan"))
            if pd.isna(val):
                rkf_values.append("")
            else:
                rkf_values.append(f"{float(val):.2f}")
        if any(val for val in rkf_values):
            lines.append(r"KP\,rk Wald F & " + " & ".join(rkf_values) + r" \\")

    return lines


def format_combined_table_chunk(
    df: pd.DataFrame,
    specs: list[str],
    idx: int,
    total_parts: int,
) -> list[str]:
    n_cols = len(specs)
    header_nums = " & ".join(f"({i})" for i in range(1, n_cols + 1))
    col_spec = _tabular_star_spec(n_cols)

    lines: list[str] = [
        f"% Auto-generated block: Combined (part {idx} of {total_parts})",
        r"{\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        rf" & \multicolumn{{{n_cols}}}{{c}}{{Contributions}} \\",
        rf"\cmidrule(lr){{2-{n_cols + 1}}}",
        " & " + header_nums + r" \\",
        r"\midrule",
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
        *panel_block(df[df.model_type == "OLS"], specs),
        r"\midrule",
        *panel_stats_block(df[df.model_type == "OLS"], specs, model="OLS"),
        r"\midrule",
        rf"\multicolumn{{{n_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
        *panel_block(df[df.model_type == "IV"], specs),
        r"\midrule",
        *panel_stats_block(df[df.model_type == "IV"], specs, model="IV"),
        r"\midrule",
        *fixed_effects_block(n_cols),
        r"\midrule",
        *controls_block(specs),
        r"\bottomrule",
        r"\end{tabular*}",
        r"}",
    ]
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
    lines_combined: list[str] = []
    for i in range(tables_needed):
        chunk = spec_order[i * COLS_PER_TABLE : (i + 1) * COLS_PER_TABLE]
        lines_combined.extend(
            format_combined_table_chunk(
                df,
                chunk,
                idx=i + 1,
                total_parts=tables_needed,
            )
        )
        lines_combined.append("")
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
    if lines_combined and lines_combined[-1] == "":
        lines_combined.pop()
    OUTPUT_TEX_BASE.write_text("\n".join(lines_combined), encoding="utf-8")
    OUTPUT_TEX_OLS.write_text("\n".join(lines_ols), encoding="utf-8")
    OUTPUT_TEX_IV.write_text("\n".join(lines_iv), encoding="utf-8")
    print(f"Wrote {OUTPUT_TEX_OLS}")
    print(f"Wrote {OUTPUT_TEX_IV}")
    print(f"Wrote {OUTPUT_TEX_BASE}")


if __name__ == "__main__":
    main()
