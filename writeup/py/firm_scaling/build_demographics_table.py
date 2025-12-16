#!/usr/bin/env python3
"""Build OLS/IV tables for firm-level demographic outcomes.

Consumes the CSV emitted by spec/stata/firm_scaling_demographics.do and
formats a LaTeX table consistent with the existing firm_scaling outputs.
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

from project_paths import RESULTS_RAW, RESULTS_CLEANED_TEX

PREAMBLE = "\\centering\n"

PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"Startup",
}

OUTCOME_HEADERS = {
    "female_hires_share": r"\makecell{Female Share\\of Hires}",
    "female_headcount_share": r"\makecell{Female Share\\of Headcount}",
    "female_join_rate": r"\makecell{Female\\Join Rate}",
    "female_leave_rate": r"\makecell{Female\\Leave Rate}",
    "avg_age_hires": r"\makecell{Avg Age\\(Hires)}",
    "avg_age_headcount": r"\makecell{Avg Age\\(Headcount)}",
}


def _digits(outcome: str) -> int:
    """Return decimal places to display based on outcome scale."""
    if outcome.startswith("avg_age"):
        return 2
    return 4  # shares/rates


def cell(coef: float, se: float, p: float, outcome: str) -> str:
    digits = _digits(outcome)
    stars = "" if pd.isna(p) else ("***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else "")
    fmt = f"{{:.{digits}f}}"
    return rf"\makecell[c]{{{fmt.format(coef)}{stars}\\({fmt.format(se)})}}"


def _panel_rows(df: pd.DataFrame, outcomes: list[str], model: str, label: str) -> list[str]:
    lines: list[str] = []
    lines.append(rf"\multicolumn{{{len(outcomes)+1}}}{{@{{}}l}}{{\textbf{{Panel {label}: {model}}}}} \\")
    lines.append(r"\addlinespace[2pt]")

    for param in ("var3", "var5", "var4"):
        row = [PARAM_LABEL[param]]
        for outcome in outcomes:
            sub = df[
                (df["param"] == param)
                & (df["outcome"] == outcome)
                & (df["model_type"] == model)
            ].head(1)
            if sub.empty:
                row.append("--")
                continue
            coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
            row.append(cell(coef, se, pval, outcome))
        lines.append(" & ".join(row) + r" \\")
    return lines


def build_table(df: pd.DataFrame, outcomes: list[str]) -> str:
    cols = len(outcomes)
    header_nums = " & " + " & ".join(f"({i})" for i in range(1, cols + 1)) + r" \\"  # noqa: E501
    header_outcomes = " & " + " & ".join(OUTCOME_HEADERS[o] for o in outcomes) + r" \\"  # noqa: E501

    lines: list[str] = []
    col_pattern = r"c@{\extracolsep{\fill}}"
    lines.append(
        rf"\begin{{tabular*}}{{\linewidth}}{{@{{}}l@{{\extracolsep{{\fill}}}}{col_pattern * (cols - 1)}c@{{}}}}"
    )
    lines.append(r"\toprule")
    lines.append(header_outcomes)
    lines.append(header_nums)
    lines.append(r"\midrule")

    # Panel A: OLS
    lines.extend(_panel_rows(df, outcomes, model="OLS", label="A"))
    lines.append(r"\midrule")
    # Panel B: IV
    lines.extend(_panel_rows(df, outcomes, model="IV", label="B"))
    lines.append(r"\midrule")

    lines.append(
        "Pre-Covid Mean"
        + " & "
        + " & ".join(
            (f"{df[(df['outcome']==o) & (df['model_type']=='OLS')]['pre_mean'].iloc[0]:.{_digits(o)}f}"
            if not df[(df['outcome']==o) & (df['model_type']=='OLS')].empty
            else "--")
            for o in outcomes
        )
        + r" \\"
    )
    lines.append(
        "KP rk Wald F"
        + " & "
        + " & ".join(
            (f"{df[(df['outcome']==o) & (df['model_type']=='IV')]['rkf'].iloc[0]:.2f}"
            if not df[(df['outcome']==o) & (df['model_type']=='IV')].empty
            else "--")
            for o in outcomes
        )
        + r" \\"
    )
    lines.append(
        "N"
        + " & "
        + " & ".join(
            f"{int(df[(df['outcome']==o) & (df['model_type']=='OLS')]['nobs'].iloc[0]):,}"
            if not df[(df['outcome']==o) & (df['model_type']=='OLS')].empty
            else "--"
            for o in outcomes
        )
        + r" \\"
    )

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    return PREAMBLE + "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build firm demographics table")
    parser.add_argument(
        "--outcomes",
        nargs="+",
        default=[
            "female_hires_share",
            "female_headcount_share",
            "female_join_rate",
            "female_leave_rate",
        ],
        help="Outcome columns to include (order preserved)",
    )
    args = parser.parse_args()

    input_csv = RESULTS_RAW / "firm_scaling_demographics" / "consolidated_results.csv"
    if not input_csv.exists():
        raise SystemExit(f"Missing results CSV: {input_csv}")

    df = pd.read_csv(input_csv)
    out_path = RESULTS_CLEANED_TEX / "firm_scaling_demographics.tex"
    table_body = build_table(df, args.outcomes)
    out_path.write_text(table_body)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
