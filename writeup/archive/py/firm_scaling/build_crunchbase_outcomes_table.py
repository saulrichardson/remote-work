#!/usr/bin/env python3
"""Format Crunchbase-based firm_scaling outcomes into a LaTeX table.

This script consumes the Stata exports produced by:
  spec/stata/firm_scaling_crunchbase.do <lhs_var>

Specifically, it reads:
  results/raw/firm_scaling_cb_cb_any_round/consolidated_results.csv
  results/raw/firm_scaling_cb_cb_log1p_raised_usd/consolidated_results.csv

and emits a paper-ready table fragment:
  results/cleaned/tex/firm_scaling_crunchbase_outcomes.tex

The goal is to present the *same RHS / FE / IV* spec as firm_scaling.do, but
with Crunchbase funding outcomes on the LHS.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir


STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOMES: list[dict[str, str]] = [
    {
        "lhs": "cb_any_round",
        "title": r"\makecell[c]{Any\\funding\\round}",
    },
    {
        "lhs": "cb_log1p_raised_usd",
        "title": r"\makecell[c]{Log(1+\\USD\\raised)}",
    },
]

OUT_PATH = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_outcomes.tex"


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def fmt_num(x: float, *, decimals: int = 2) -> str:
    # Guard against "-0.00"
    if abs(x) < 0.5 * (10 ** (-decimals)):
        x = 0.0
    return f"{x:.{decimals}f}"


def coef_cell(row: pd.Series) -> str:
    coef = float(row["coef"])
    se = float(row["se"])
    pval = float(row["pval"])
    return rf"\makecell[c]{{{fmt_num(coef)}{stars(pval)}\\({fmt_num(se)})}}"


def require_columns(df: pd.DataFrame, path: Path) -> None:
    required = {"model_type", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "nobs"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {path}.")


def load_spec(lhs: str) -> pd.DataFrame:
    csv_path = RESULTS_RAW / f"firm_scaling_cb_{lhs}" / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing raw results: {csv_path}. "
            f"Run: do spec/stata/firm_scaling_crunchbase.do {lhs}"
        )
    df = pd.read_csv(csv_path)
    require_columns(df, csv_path)
    return df


def pick_row(df: pd.DataFrame, model: str, param: str) -> pd.Series | None:
    sub = df[(df["model_type"] == model) & (df["param"] == param)].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def stat_value(df: pd.DataFrame, model: str, field: str) -> float | None:
    sub = df[df["model_type"] == model].head(1)
    if sub.empty:
        return None
    val = sub.iloc[0].get(field)
    if pd.isna(val):
        return None
    return float(val)


def table_fragment(specs: dict[str, pd.DataFrame]) -> str:
    num_cols = len(OUTCOMES)
    col_spec = "@{}l" + "@{\\extracolsep{\\fill}}" + "c" * num_cols + "@{}"

    header_titles = " & ".join([o["title"] for o in OUTCOMES])
    header_nums = " & ".join([f"({i})" for i in range(1, num_cols + 1)])

    cmidrules = []
    for j in range(num_cols):
        col = 2 + j
        cmidrules.append(rf"\cmidrule(lr){{{col}-{col}}}")

    lines: list[str] = []
    lines.append(r"\centering")
    lines.append(rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}")
    lines.append(r"\toprule")
    lines.append(rf" & {header_titles} \\")
    lines.append("\n".join(cmidrules))
    lines.append(rf" & {header_nums} \\")
    lines.append(r"\midrule")

    # Panel A: OLS ---------------------------------------------------------
    lines.append(r"\multicolumn{" + str(1 + num_cols) + r"}{@{}l}{\textbf{\uline{Panel A: OLS}}} \\")
    lines.append(r"\addlinespace[2pt]")

    for param in PARAM_ORDER:
        row_cells = [r"\hspace{1em}" + PARAM_LABEL[param]]
        for o in OUTCOMES:
            lhs = o["lhs"]
            row = pick_row(specs[lhs], "OLS", param)
            row_cells.append(coef_cell(row) if row is not None else "--")
        lines.append(" & ".join(row_cells) + r" \\")

    lines.append(r"\midrule")
    # Pre mean and N from OLS (consistent with other firm_scaling tables)
    pre_vals = []
    n_vals = []
    for o in OUTCOMES:
        lhs = o["lhs"]
        pre = stat_value(specs[lhs], "OLS", "pre_mean")
        n = stat_value(specs[lhs], "OLS", "nobs")
        pre_vals.append(fmt_num(pre) if pre is not None else "")
        n_vals.append(f"{int(n):,}" if n is not None else "")

    lines.append(" & ".join(["Pre-Covid Mean", *pre_vals]) + r" \\")
    lines.append(" & ".join(["N", *n_vals]) + r" \\")

    # Panel B: IV ----------------------------------------------------------
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{" + str(1 + num_cols) + r"}{@{}l}{\textbf{\uline{Panel B: IV}}} \\")
    lines.append(r"\addlinespace[2pt]")

    for param in PARAM_ORDER:
        row_cells = [r"\hspace{1em}" + PARAM_LABEL[param]]
        for o in OUTCOMES:
            lhs = o["lhs"]
            row = pick_row(specs[lhs], "IV", param)
            row_cells.append(coef_cell(row) if row is not None else "--")
        lines.append(" & ".join(row_cells) + r" \\")

    lines.append(r"\midrule")
    rkf_vals = []
    n_vals = []
    for o in OUTCOMES:
        lhs = o["lhs"]
        rkf = stat_value(specs[lhs], "IV", "rkf")
        n = stat_value(specs[lhs], "IV", "nobs")
        rkf_vals.append(fmt_num(rkf) if rkf is not None else "")
        n_vals.append(f"{int(n):,}" if n is not None else "")

    lines.append(" & ".join(["KP rk Wald F", *rkf_vals]) + r" \\")
    lines.append(" & ".join(["N", *n_vals]) + r" \\")

    # Fixed effects footer -------------------------------------------------
    checks = " & ".join([r"$\checkmark$"] * num_cols)
    lines.append(r"\midrule")
    lines.append(r"\textbf{Fixed Effects} & " + " & ".join([""] * num_cols) + r" \\")
    lines.append(r"\hspace{1em}Time & " + checks + r" \\")
    lines.append(r"\hspace{1em}Firm & " + checks + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def main() -> None:
    specs: dict[str, pd.DataFrame] = {o["lhs"]: load_spec(o["lhs"]) for o in OUTCOMES}

    ensure_dir(RESULTS_CLEANED_TEX)
    OUT_PATH.write_text(table_fragment(specs), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
