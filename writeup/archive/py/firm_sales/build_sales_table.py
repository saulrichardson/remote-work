#!/usr/bin/env python3
"""Build the firm-sales table (Data Axle) for the mini-writeup.

Inputs:
  - results/raw/firm_sales/consolidated_results.csv (from spec/stata/firm_sales.do)

Outputs:
  - results/cleaned/tex/firm_sales.tex
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

RAW_SPEC = RESULTS_RAW / "firm_sales" / "consolidated_results.csv"
OUT_TEX = RESULTS_CLEANED_TEX / "firm_sales.tex"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOMES: Sequence[tuple[str, str]] = (
    ("ln_sales_loc_max_we", "Location Sales"),
    ("ln_parent_sales_max_we", "Parent Sales"),
)

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


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


def coef_cell(row: pd.Series) -> str:
    coef, se, pval = row[["coef", "se", "pval"]]
    return rf"\makecell[c]{{{coef:.3f}{stars(pval)}\\({se:.3f})}}"


def fetch_entry(df: pd.DataFrame, *, model: str, outcome: str, param: str) -> pd.Series:
    sub = df[
        (df["model_type"] == model) & (df["outcome"] == outcome) & (df["param"] == param)
    ].head(1)
    if sub.empty:
        raise KeyError(f"Missing row: model={model} outcome={outcome} param={param}")
    return sub.iloc[0]


def stat_value(df: pd.DataFrame, *, model: str, outcome: str, field: str) -> float | None:
    sub = df[(df["model_type"] == model) & (df["outcome"] == outcome)].head(1)
    if sub.empty:
        return None
    value = sub.iloc[0].get(field)
    if pd.isna(value):
        return None
    return float(value)


def build_panel_rows(df: pd.DataFrame, *, model: str) -> list[str]:
    indent = r"\hspace{1em}"
    lines: list[str] = []
    for param in PARAM_ORDER:
        row_cells = [indent + PARAM_LABEL[param]]
        for outcome, _ in OUTCOMES:
            entry = fetch_entry(df, model=model, outcome=outcome, param=param)
            row_cells.append(coef_cell(entry))
        lines.append(" & ".join(row_cells) + r" \\")
    return lines


def build_stats_rows(df: pd.DataFrame, *, model: str) -> list[str]:
    labels: list[tuple[str, str, str]] = []
    if model == "OLS":
        labels.append(("Pre-Covid Mean", "pre_mean", "{:.2f}"))
    if model == "IV":
        labels.append(("KP rk Wald F", "rkf", "{:.2f}"))
    labels.append(("N", "nobs", "{:,.0f}"))

    rows: list[str] = []
    for label, field, fmt in labels:
        values: list[str] = []
        for outcome, _ in OUTCOMES:
            value = stat_value(df, model=model, outcome=outcome, field=field)
            values.append("" if value is None else fmt.format(value))
        rows.append(" & ".join([label, *values]) + r" \\")
    return rows


def fixed_effect_rows(num_cols: int) -> list[str]:
    checks = " & ".join([r"$\checkmark$"] * num_cols)
    indent = r"\hspace{1em}"
    return [
        r"\textbf{Fixed Effects} & " + " & ".join([""] * num_cols) + r" \\",
        indent + r"Time & " + checks + r" \\",
        indent + r"Firm & " + checks + r" \\",
    ]


def build_table(df: pd.DataFrame) -> str:
    num_cols = len(OUTCOMES)
    col_fmt = column_format(num_cols)

    header_cells = [""] + [label for _, label in OUTCOMES]
    header = " & ".join(header_cells) + r" \\"
    header_nums = " & " + " & ".join(f"({i})" for i in range(1, num_cols + 1)) + r" \\"

    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_fmt}}}",
        r"\toprule",
        header,
        header_nums,
        r"\midrule",
        rf"\multicolumn{{{num_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
        *build_panel_rows(df, model="OLS"),
        r"\midrule",
        *build_stats_rows(df, model="OLS"),
        r"\midrule",
        rf"\multicolumn{{{num_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
        *build_panel_rows(df, model="IV"),
        r"\midrule",
        *build_stats_rows(df, model="IV"),
        r"\midrule",
        *fixed_effect_rows(num_cols),
        r"\bottomrule",
        r"\end{tabular*}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    if not RAW_SPEC.exists():
        raise SystemExit(
            "Missing raw results.\n"
            f"Expected: {RAW_SPEC}\n"
            "Run in Stata:  do spec/stata/firm_sales.do"
        )

    df = pd.read_csv(RAW_SPEC)
    required_cols = {"model_type", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "nobs"}
    missing = required_cols - set(df.columns)
    if missing:
        raise SystemExit(f"{RAW_SPEC} missing columns: {sorted(missing)}")

    # Keep only parameters we show in the table; fail if anything is missing.
    df = df[df["param"].isin(PARAM_ORDER)].copy()

    # Ensure we have exactly the cells we need.
    needed = []
    for model in ["OLS", "IV"]:
        for outcome, _ in OUTCOMES:
            for param in PARAM_ORDER:
                needed.append((model, outcome, param))
    present = {
        (r["model_type"], r["outcome"], r["param"])
        for _, r in df.iterrows()
        if r["model_type"] in {"OLS", "IV"}
    }
    missing_cells = [t for t in needed if t not in present]
    if missing_cells:
        preview = "\n".join(f"  {m}" for m in missing_cells[:10])
        raise SystemExit(f"Missing required result rows (showing up to 10):\n{preview}")

    table = build_table(df)
    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_TEX.write_text(table)
    print(f"Wrote {OUT_TEX}")


if __name__ == "__main__":
    main()
