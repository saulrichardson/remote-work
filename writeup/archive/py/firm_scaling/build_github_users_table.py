#!/usr/bin/env python3
"""Format firm-scaling results computed from GitHub-linked users (option B).

This script reads the Stata export produced by:

    spec/stata/firm_scaling_github_users.do <variant>

and writes a mini-writeup-ready LaTeX table under results/cleaned/tex.

The intent is to mirror the look/feel of the existing firm-scaling tables
(`build_growth_split_tables.py`) while using the GitHub-user outcomes:
growth/join/leave rates computed by collapsing the user panel to firm×half-year.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

RAW_DIR = RESULTS_RAW
FINAL_TEX_DIR = RESULTS_CLEANED_TEX

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

OUTCOME_LABEL = {
    "growth_rate_we": "Growth",
    "join_rate_we": "Join",
    "leave_rate_we": "Leave",
}


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def column_format(n_numeric: int) -> str:
    parts = ["@{}l"]
    parts.extend([r"@{\extracolsep{\fill}}c"] * n_numeric)
    parts.append("@{}")
    return "".join(parts)


def coef_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def fetch_entry(df: pd.DataFrame, model: str, outcome: str, param: str) -> pd.Series | None:
    sub = df[
        (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["param"] == param)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def stat_value(
    df: pd.DataFrame,
    model: str,
    outcome: str,
    field: str,
    fmt: str,
) -> str:
    sub = df[(df["model_type"] == model) & (df["outcome"] == outcome)].head(1)
    if sub.empty:
        return ""
    value = sub.iloc[0].get(field)
    if pd.isna(value):
        return ""
    return fmt.format(value)


def build_table(df: pd.DataFrame, outcomes: list[str]) -> str:
    ncols = len(outcomes)
    col_fmt = column_format(ncols)

    header_groups = " & ".join(["", *[OUTCOME_LABEL[o] for o in outcomes]]) + r" \\"
    header_nums = " & " + " & ".join(f"({i})" for i in range(1, ncols + 1)) + r" \\"
    cmid = r"\cmidrule(lr){2-" + str(ncols + 1) + "}"

    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_fmt}}}",
        r"\toprule",
        header_groups,
        cmid,
        header_nums,
        r"\midrule",
        rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
    ]

    INDENT = r"\hspace{1em}"
    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABEL[param]]
        for outcome in outcomes:
            entry = fetch_entry(df, "OLS", outcome, param)
            row.append(
                coef_cell(float(entry["coef"]), float(entry["se"]), float(entry["pval"]))
                if entry is not None
                else "--"
            )
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    pre = [
        stat_value(df, "OLS", outcome, "pre_mean", "{:.2f}") for outcome in outcomes
    ]
    nobs = [
        stat_value(df, "OLS", outcome, "nobs", "{:,}") for outcome in outcomes
    ]
    lines.append(" & ".join(["Pre-Covid Mean", *pre]) + r" \\")
    lines.append(" & ".join(["N", *nobs]) + r" \\")

    lines.append(r"\midrule")
    lines.append(
        rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\"
    )
    lines.append(r"\addlinespace[2pt]")

    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABEL[param]]
        for outcome in outcomes:
            entry = fetch_entry(df, "IV", outcome, param)
            row.append(
                coef_cell(float(entry["coef"]), float(entry["se"]), float(entry["pval"]))
                if entry is not None
                else "--"
            )
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    rkf = [
        stat_value(df, "IV", outcome, "rkf", "{:.2f}") for outcome in outcomes
    ]
    nobs_iv = [
        stat_value(df, "IV", outcome, "nobs", "{:,}") for outcome in outcomes
    ]
    lines.append(" & ".join(["KP rk Wald F", *rkf]) + r" \\")
    lines.append(" & ".join(["N", *nobs_iv]) + r" \\")

    lines.append(r"\midrule")
    lines.append(" & ".join([r"\textbf{Fixed Effects}", *[""] * ncols]) + r" \\")
    lines.append(
        r"\hspace{1em}Firm & " + " & ".join([r"$\checkmark$"] * ncols) + r" \\"
    )
    lines.append(
        r"\hspace{1em}Half-year & " + " & ".join([r"$\checkmark$"] * ncols) + r" \\"
    )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")

    return "\n".join(lines) + "\n"


def load_results(variant: str) -> pd.DataFrame:
    path = RAW_DIR / f"firm_scaling_github_users_{variant}" / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing raw results {path}. Run spec/stata/firm_scaling_github_users.do {variant}."
        )
    df = pd.read_csv(path)
    required = {"model_type", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "nobs"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Unexpected columns in {path}; missing {sorted(missing)}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Format firm_scaling (GitHub-linked users) table")
    parser.add_argument("--variant", default="precovid", help="User-panel variant (default: precovid)")
    args = parser.parse_args()

    df = load_results(args.variant)
    outcomes = ["growth_rate_we", "join_rate_we", "leave_rate_we"]
    table = build_table(df, outcomes)

    out_path = FINAL_TEX_DIR / f"firm_scaling_github_users_{args.variant}.tex"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(table)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

