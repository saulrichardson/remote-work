#!/usr/bin/env python3
"""Format the hire-selection two-column table for the mini-writeup.

Inputs:
  results/raw/user_hire_selection_<variant>/selection_results.csv
Outputs:
  results/cleaned/tex/user_hire_selection_<variant>.tex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

# Path bootstrap (mirror other formatters)
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir

PARAM_ORDER: Iterable[str] = ("var3", "var5", "var4")
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_results(variant: str) -> pd.DataFrame:
    path = RESULTS_RAW / f"user_hire_selection_{variant}" / "selection_results.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    return df


def build_table(df: pd.DataFrame) -> str:
    # ensure order
    outcomes = ["old_prod", "delta_prod"]
    headers = {
        "old_prod": r"Prior Prod. (2 halves pre)",
        "delta_prod": r"$\Delta$ Prod. (2 halves post $-$ pre)",
    }

    lines: list[str] = []
    lines.append("% Auto-generated – do not edit")
    lines.append(r"\centering")
    lines.append(r"\begin{tabular}{@{}lcc@{}}")
    lines.append(r"\toprule")
    lines.append(r"Variables & " + " & ".join(headers[o] for o in outcomes) + r" \\")
    lines.append(r"\midrule")

    for p in PARAM_ORDER:
        row = [PARAM_LABEL.get(p, p)]
        for o in outcomes:
            sub = df[(df["outcome"] == o) & (df["param"] == p)]
            if sub.empty:
                row.append("--")
            else:
                rec = sub.iloc[0]
                row.append(cell(rec.coef, rec.se, rec.pval))
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    # Summary rows
    pre_means = []
    for o in outcomes:
        sub = df[df["outcome"] == o]
        pre_means.append(f"{sub['pre_mean'].iloc[0]:.2f}" if not sub.empty else "--")
    lines.append("Pre-Covid Mean & " + " & ".join(pre_means) + r" \\")

    n_obs = int(df["nobs"].iloc[0]) if "nobs" in df.columns else None
    if n_obs:
        lines.append(rf"N & {n_obs:,} & {n_obs:,} \\")

    lines.append(r"\midrule")
    lines.append(r"\textbf{Fixed Effects} &  &  \\")
    lines.append(r"\hspace{1em}Hire half-year & $\checkmark$ & $\checkmark$ \\")
    lines.append(r"\textbf{Clusters} & \multicolumn{2}{c}{Firm (new employer)} \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hire-selection regression table.")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="Panel variant (default: %(default)s)",
    )
    args = parser.parse_args()

    df = load_results(args.variant)
    table_tex = build_table(df)

    out_path = RESULTS_CLEANED_TEX / f"user_hire_selection_{args.variant}.tex"
    ensure_dir(out_path.parent)
    out_path.write_text(table_tex)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
