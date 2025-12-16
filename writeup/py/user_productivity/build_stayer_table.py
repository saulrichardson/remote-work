#!/usr/bin/env python3
"""Generate OLS + IV table for the stayer-only user-productivity sample."""

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


STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
DASH = r"--"
TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
TABLE_WIDTH = r"\linewidth"
TABLE_ENV = "tabular*"
PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def column_format(n_numeric: int) -> str:
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"


def build_headers() -> tuple[str, str, str]:
    header_nums = " & (1)" + r" \\"
    header_groups = " & Contribution Rank" + r" \\"
    cmidrule_line = r"\cmidrule(lr){2-2}"
    return header_nums, header_groups, cmidrule_line


def stat_row(df: pd.DataFrame, model: str, label: str, field: str, fmt: str) -> str:
    sub = df[(df["model_type"] == model)].head(1)
    if sub.empty:
        val = DASH
    else:
        raw_val = sub.iloc[0].get(field)
        val = fmt.format(raw_val) if pd.notna(raw_val) else DASH
    return " & ".join([label, val]) + r" \\"


def fe_block() -> list[str]:
    rows: list[str] = []
    INDENT = r"\hspace{1em}"
    check = r"$\checkmark$"
    rows.append(r"\textbf{Fixed Effects} &  \\")
    rows.append(" & ".join([INDENT + "Time", check]) + r" \\")
    rows.append(" & ".join([INDENT + "Firm", check]) + r" \\")
    rows.append(" & ".join([INDENT + "Individual", check]) + r" \\")
    return rows


def build_table(df: pd.DataFrame) -> str:
    header_nums, header_groups, cmidrule_line = build_headers()
    col_fmt = column_format(1)

    INDENT = r"\hspace{1em}"

    ols_rows: list[str] = [
        rf"\multicolumn{{2}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
    ]
    for param in PARAM_ORDER:
        sub = df[
            (df["model_type"] == "OLS")
            & (df["param"] == param)
            & (df["outcome"] == "total_contributions_q100")
        ].head(1)
        if sub.empty:
            cell_val = DASH
        else:
            coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
            cell_val = cell(coef, se, pval)
        ols_rows.append(" & ".join([INDENT + PARAM_LABEL[param], cell_val]) + r" \\")

    iv_rows: list[str] = [
        rf"\multicolumn{{2}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
    ]
    for param in PARAM_ORDER:
        sub = df[
            (df["model_type"] == "IV")
            & (df["param"] == param)
            & (df["outcome"] == "total_contributions_q100")
        ].head(1)
        if sub.empty:
            cell_val = DASH
        else:
            coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
            cell_val = cell(coef, se, pval)
        iv_rows.append(" & ".join([INDENT + PARAM_LABEL[param], cell_val]) + r" \\")

    pre_mean = stat_row(df, "OLS", "Pre-Covid Mean", "pre_mean", "{:.2f}")
    kp_row = stat_row(df, "IV", "KP rk Wald F", "rkf", "{:.2f}")
    n_row_ols = stat_row(df, "OLS", "N", "nobs", "{:,}")
    n_row_iv = stat_row(df, "IV", "N (IV)", "nobs", "{:,}")

    lines = [
        rf"\begin{{{TABLE_ENV}}}{{{TABLE_WIDTH}}}{{{col_fmt}}}",
        TOP,
        header_groups,
        cmidrule_line,
        header_nums,
        MID,
        *ols_rows,
        *iv_rows,
        MID,
        pre_mean,
        kp_row,
        n_row_ols,
        n_row_iv,
        MID,
        *fe_block(),
        BOTTOM,
        rf"\end{{{TABLE_ENV}}}",
    ]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create stayer-only regression table for user productivity")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="User panel variant to load (default: %(default)s)",
    )
    args = parser.parse_args()

    raw_dir = RESULTS_RAW / f"user_productivity_{args.variant}_stayer"
    input_path = raw_dir / "consolidated_results.csv"
    if not input_path.exists():
        raise SystemExit(f"Missing stayer results: {input_path}")

    df = pd.read_csv(input_path)

    table_body = build_table(df).rstrip()
    output_path = RESULTS_CLEANED_TEX / f"user_productivity_{args.variant}_stayer.tex"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\\centering\n" + table_body + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
