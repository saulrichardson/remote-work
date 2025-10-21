#!/usr/bin/env python3
"""Generate the firm×user + time FE first-stage table for the user-productivity IV.

The alternative-FE Stata driver (`spec/user_productivity_alternative_fe.do`) stores
first-stage statistics for each fixed-effect configuration in
``results/raw/user_productivity_alternative_fe_<variant>/first_stage_fstats.csv``.

This script filters the rows associated with the "firmbyuseryh" tag (firm × user +
period fixed effects) and reshapes them into a two-column LaTeX table that mirrors
other first-stage tables in the mini-report.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

VARIANT_CHOICES = ["unbalanced", "balanced", "precovid", "balanced_pre"]
DEFAULT_VARIANT = "precovid"
TARGET_FE_TAG = "firmbyuseryh"
TARGET_OUTCOME = "total_contributions_q100"

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create firm×user+time first-stage table")
    parser.add_argument(
        "--variant",
        choices=VARIANT_CHOICES,
        default=DEFAULT_VARIANT,
        help="User panel variant used in the alternative-FE run.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional override for the output .tex path.",
    )
    return parser.parse_args()


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, pval: float) -> str:
    """Return a centred makecell containing the coefficient and standard error."""
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


COL_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

PARAM_LABEL = {
    "var6": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) $",
    "var7": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

ENDOVARS = ["var3", "var5"]
PARAMS = ["var6", "var7", "var4"]


def main() -> None:
    args = parse_args()

    src_dir = (
        PROJECT_ROOT
        / "results"
        / "raw"
        / f"user_productivity_alternative_fe_{args.variant}"
    )
    input_csv = src_dir / "first_stage_fstats.csv"
    if not input_csv.exists():
        raise FileNotFoundError(f"Missing first-stage CSV: {input_csv}")

    df = pd.read_csv(input_csv)
    mask = (df["fe_tag"] == TARGET_FE_TAG) & (df["outcome"] == TARGET_OUTCOME)
    fs = df.loc[mask].copy()
    if fs.empty:
        available_tags = sorted(df["fe_tag"].unique())
        raise ValueError(
            f"No rows found for fe_tag='{TARGET_FE_TAG}' and outcome='{TARGET_OUTCOME}'."
            f" Available fe_tag values: {available_tags}"
        )

    # Build LaTeX table -----------------------------------------------------------------
    variant_tex = args.variant.replace("_", r"\_")
    caption = (
        "First-Stage Estimates -- User Productivity "
        f"({variant_tex}, firm$\times$user + time FE)"
    )
    label = f"tab:user_productivity_{args.variant}_firmbyuseryh_first_stage"

    lines: list[str] = []
    lines.append("% Auto-generated – do *not* edit by hand")
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(rf"\caption{{{caption}}}")
    lines.append(rf"\label{{{label}}}")

    col_spec = "l" + "c" * len(ENDOVARS)
    lines.append(rf"\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"\toprule")
    header = [""] + [COL_LABEL.get(var, var) for var in ENDOVARS]
    lines.append(" & ".join(header) + r"\\")
    lines.append(r"\midrule")

    for param in PARAMS:
        row = [PARAM_LABEL.get(param, param)]
        for endo in ENDOVARS:
            match = fs[(fs["param"] == param) & (fs["endovar"] == endo)]
            if match.empty:
                row.append("")
            else:
                vals = match.iloc[0]
                row.append(cell(vals.coef, vals.se, vals.pval))
        lines.append(" & ".join(row) + r"\\")

    lines.append(r"\midrule")
    span = 1 + len(ENDOVARS)
    lines.append(
        rf"\multicolumn{{{span}}}{{l}}{{\textit{{Fixed effects: firm $\times$ user + time}}}}\\"
    )
    lines.append(r"\midrule")

    def first_value(col: str, endo: str) -> float:
        match = fs[fs["endovar"] == endo]
        if match.empty:
            return float("nan")
        return match.iloc[0][col]

    summary_rows = {
        "Partial F": [first_value("partialF", e) for e in ENDOVARS],
        "N": [int(first_value("nobs", e)) for e in ENDOVARS],
    }
    for label_text, values in summary_rows.items():
        formatted = []
        for value in values:
            if isinstance(value, (int, float)) and not pd.isna(value):
                if label_text == "Partial F":
                    formatted.append(f"{value:.2f}")
                else:
                    formatted.append(f"{value:,}")
            else:
                formatted.append("")
        lines.append(" & ".join([label_text] + formatted) + r"\\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    output_path = args.out or (
        PROJECT_ROOT
        / "results"
        / "cleaned"
        / f"user_productivity_{args.variant}_firmbyuseryh_first_stage.tex"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote LaTeX table to {output_path}")


if __name__ == "__main__":
    main()
