#!/usr/bin/env python3
"""Format user wage specification output into a LaTeX table."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import math

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PARAM_LABELS: list[Tuple[str, str]] = [
    ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
    ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
    ("var4", r"$ \mathds{1}(\text{Post}) \times \text{Startup} $"),
]

OUTCOME_LABEL = r"$\log(\text{Salary})$"

STAR_LEVELS: list[Tuple[float, str]] = [
    (0.01, "***"),
    (0.05, "**"),
    (0.10, "*"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def significance_stars(pval: float) -> str:
    if math.isnan(pval):
        return ""
    for cut, sym in STAR_LEVELS:
        if pval <= cut:
            return sym
    return ""


def clean_number(x: float, decimals: int) -> str:
    if math.isnan(x):
        return "-"
    if abs(x) < 10 ** (-(decimals + 1)):
        x = 0.0
    return f"{x:.{decimals}f}"


def format_coef(coef: float, se: float, pval: float) -> Tuple[str, str]:
    stars = significance_stars(pval)
    coef_str = f"{clean_number(coef, 3)}{stars}"
    se_str = f"({clean_number(se, 3)})"
    return coef_str, se_str


def extract_row(df: pd.DataFrame, model: str, param: str) -> pd.Series | None:
    subset = df.loc[(df["model_type"] == model) & (df["param"] == param)]
    if subset.empty:
        return None
    return subset.iloc[0]


def format_entry(row: pd.Series | None) -> Tuple[str, str]:
    if row is None:
        return "", ""
    coef, se = format_coef(row["coef"], row["se"], row["pval"])
    return coef, se


def build_table(df: pd.DataFrame, *, caption: str, label: str) -> str:
    # Ensure required models exist
    models = set(df["model_type"].unique())
    if not {"OLS", "IV"} <= models:
        raise ValueError("Expected both OLS and IV model results in consolidated_results.csv")

    # Pre-COVID mean and N (assume identical across params within model)
    row_ols = extract_row(df, "OLS", "var3")
    row_iv = extract_row(df, "IV", "var3")
    if row_ols is None or row_iv is None:
        raise ValueError("Missing var3 coefficients for OLS or IV in consolidated_results.csv")

    pre_mean_ols = clean_number(row_ols["pre_mean"], 2)
    pre_mean_iv = clean_number(row_iv["pre_mean"], 2)

    n_ols = f"{int(row_ols['nobs']):,}" if not math.isnan(row_ols["nobs"]) else "-"
    n_iv = f"{int(row_iv['nobs']):,}" if not math.isnan(row_iv["nobs"]) else "-"

    rkf_iv = clean_number(row_iv["rkf"], 1) if not math.isnan(row_iv["rkf"]) else "-"

    table_lines: List[str] = []
    table_lines.append("% Auto-generated from consolidated_results.csv")
    table_lines.append(r"\documentclass[11pt]{article}")
    table_lines.append(r"\usepackage[margin=1in]{geometry}")
    table_lines.append(r"\usepackage{booktabs}")
    table_lines.append(r"\usepackage{float}")
    table_lines.append(r"\usepackage{threeparttable}")
    table_lines.append(r"\usepackage{adjustbox}")
    table_lines.append(r"\usepackage{amsmath}")
    table_lines.append(r"\usepackage{dsfont}")
    table_lines.append(r"\begin{document}")
    table_lines.append(r"\section*{Summary}")
    table_lines.append(
        r"\noindent Outcome: log salary per worker per half-year. Specification: the same triple-difference design as the productivity spec, reported as OLS and IV estimates for Remote$\times$Post and its startup interaction."
    )
    table_lines.append(r"\bigskip")
    table_lines.append(r"\begin{table}[H]")
    table_lines.append(r"\centering")
    table_lines.append(f"\\caption{{{caption}}}")
    table_lines.append(f"\\label{{{label}}}")
    table_lines.append(r"\begin{threeparttable}")
    table_lines.append(r"\begin{adjustbox}{max width=\textwidth}")
    table_lines.append(r"\begin{tabular}{@{}lcc@{}}")
    table_lines.append(r"\toprule")
    table_lines.append(r" & OLS & IV \\")
    table_lines.append(r"\midrule")
    params_list = list(PARAM_LABELS)
    for idx, (param, label) in enumerate(params_list):
        coef_ols, se_ols = format_entry(extract_row(df, "OLS", param))
        coef_iv, se_iv = format_entry(extract_row(df, "IV", param))
        table_lines.append(f"{label} & {coef_ols} & {coef_iv} \\\\")
        table_lines.append(f" & {se_ols} & {se_iv} \\\\")
        if idx != len(params_list) - 1:
            table_lines.append(r"\addlinespace[0.35em]")
    table_lines.append(r"\midrule")
    table_lines.append(f"N & {n_ols} & {n_iv} \\\\")
    table_lines.append(f"Pre-COVID Mean & {pre_mean_ols} & {pre_mean_iv} \\\\")
    table_lines.append(f"KP rk Wald F & -- & {rkf_iv} \\\\")
    table_lines.append(r"\bottomrule")
    table_lines.append(r"\end{tabular}")
    table_lines.append(r"\end{adjustbox}")
    table_lines.append(r"\begin{tablenotes}[flushleft]")
    table_lines.append(r"\footnotesize")
    table_lines.append(
        r"\item \textit{Notes:} All models include worker, firm, and half-year fixed effects. "
        r"Standard errors clustered by worker. IV columns instrument remote exposure using firm teleworkability interactions."
    )
    table_lines.append(r"\end{tablenotes}")
    table_lines.append(r"\end{threeparttable}")
    table_lines.append(r"\end{table}")
    table_lines.append(r"\end{document}")

    return "\n".join(table_lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Format user wage results into LaTeX.")
    parser.add_argument(
        "spec_dir",
        type=Path,
        help="Directory containing consolidated_results.csv (e.g. results/raw/user_wage_precovid)",
    )
    parser.add_argument("--caption", default=None, help="Custom table caption")
    parser.add_argument("--label", default=None, help="Custom LaTeX label")
    parser.add_argument("--out", type=Path, default=None, help="Destination .tex file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_dir: Path = args.spec_dir.resolve()
    csv_path = spec_dir / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found")

    df = pd.read_csv(csv_path)

    spec_name = spec_dir.name
    if args.caption:
        caption = args.caption
    else:
        caption = "User Wage Results" if spec_name.startswith("user_wage") else spec_name.replace("_", " ").title()
    label = args.label or f"tab:{spec_name}"

    tex = build_table(df, caption=caption, label=label)

    if args.out is not None:
        out_path = args.out
    else:
        out_path = spec_dir.parents[1] / "cleaned" / f"{spec_name}.tex"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex)
    print(f"✓ Wrote {out_path}")


if __name__ == "__main__":
    main()
