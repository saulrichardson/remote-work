#!/usr/bin/env python3
"""Create a LaTeX table for fully-remote focused comparisons."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

import math
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_FINAL_TEX, RESULTS_RAW

RAW_DIR = RESULTS_RAW
FINAL_TEX_DIR = RESULTS_FINAL_TEX

COMPARISON_COLUMNS = OrderedDict(
    [
        (
            "fr_vs_hyb_match",
            {
                "suffix": "fr_vs_hyb",
                "group": "Hybrid",
                "fe_tag": "match",
            },
        ),
        (
            "fr_vs_hyb_regular",
            {
                "suffix": "fr_vs_hyb",
                "group": "Hybrid",
                "fe_tag": "regular",
            },
        ),
        (
            "fr_vs_all_match",
            {
                "suffix": "fr_vs_all",
                "group": "Hybrid/In-Person",
                "fe_tag": "match",
            },
        ),
        (
            "fr_vs_all_regular",
            {
                "suffix": "fr_vs_all",
                "group": "Hybrid/In-Person",
                "fe_tag": "regular",
            },
        ),
    ]
)

PARAM_LABELS_LATEX = {
    "var3": r"$ \text{Fully Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Fully Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float | None) -> str:
    if p is None or math.isnan(p):
        return ""
    for cut, symbol in STAR_RULES:
        if p < cut:
            return symbol
    return ""


def fmt_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_comparison(variant: str, suffix: str, fe_tag: str) -> dict:
    base_dir = RAW_DIR / f"user_productivity_fr_focus_{variant}_{suffix}"
    csv_path = base_dir / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing results for {variant}/{suffix}: {csv_path}")

    df = pd.read_csv(csv_path)
    if "fe_tag" not in df.columns:
        raise ValueError(
            "Expected `fe_tag` column in consolidated results. "
            "Re-run spec/stata/user_productivity_discrete_fr_focus.do to refresh outputs."
        )
    sub = df[(df["comparison"] == suffix) & (df["fe_tag"] == fe_tag)]
    if sub.empty:
        raise ValueError(f"No rows for suffix={suffix}, fe_tag={fe_tag}")

    var3_name = f"var3_{suffix}"
    var5_name = f"var5_{suffix}"

    out: dict[str, dict[str, pd.Series] | float | int | None] = {"OLS": {}, "IV": {}}
    for model in ("OLS", "IV"):
        model_block = sub[sub["model_type"] == model]
        for param, name in (("var3", var3_name), ("var5", var5_name)):
            row = model_block[model_block["param"] == name]
            if row.empty:
                raise ValueError(f"Missing {name} for {suffix} ({model})")
            out[model][param] = row.iloc[0]

    any_ols = out["OLS"]["var3"]  # type: ignore[index]
    any_iv = out["IV"]["var3"]    # type: ignore[index]
    out["pre_mean"] = float(any_ols.pre_mean)
    out["nobs"] = int(any_ols.nobs)
    out["rkf"] = float(any_iv.rkf) if not math.isnan(any_iv.rkf) else None
    out["comparison_group"] = str(any_ols.comparison_group)
    out["comparison"] = str(any_ols.comparison)
    out["fe_tag"] = fe_tag
    return out


def build_table(variant: str, comparisons: Iterable[str]) -> str:
    comparisons = list(comparisons)
    data = {
        key: load_comparison(
            variant,
            COMPARISON_COLUMNS[key]["suffix"],
            COMPARISON_COLUMNS[key]["fe_tag"],
        )
        for key in comparisons
    }

    lines: list[str] = []
    lines.append("% Auto-generated: user productivity fully-remote comparisons")
    colspec = "@{}l" + len(comparisons) * r"@{\extracolsep{\fill}}c" + "@{}"
    lines.append(rf"\begin{{tabular*}}{{\linewidth}}{{{colspec}}}")
    E = r"\\"
    lines.append(r"\toprule")
    header_top = ["", "\\multicolumn{{{}}}{{c}}{{Contribution Rank}}".format(len(comparisons))]
    lines.append(" & ".join(header_top) + f" {E}")
    lines.append("\\cmidrule(lr){2-%d}" % (len(comparisons) + 1))
    numbers = " & ".join(f"({i})" for i in range(1, len(comparisons) + 1))
    lines.append(" & " + numbers + f" {E}")
    lines.append(r"\midrule")

    lines.append(rf"\multicolumn{{{len(comparisons)+1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} {E}")
    lines.append(r"\addlinespace[2pt]")
    indent = r"\hspace{1em}"
    for param in ("var3", "var5"):
        label = PARAM_LABELS_LATEX[param]
        row_cells = [fmt_cell(float(data[cmp]["OLS"][param].coef), float(data[cmp]["OLS"][param].se), float(data[cmp]["OLS"][param].pval)) for cmp in comparisons]  # type: ignore[index]
        lines.append(f"{indent}{label} & " + " & ".join(row_cells) + f" {E}")
    lines.append(r"\midrule")
    lines.append("Pre-Covid Mean & " + " & ".join(f"{data[c]['pre_mean']:.2f}" for c in comparisons) + f" {E}")
    lines.append("N & " + " & ".join(f"{data[c]['nobs']:,}" for c in comparisons) + f" {E}")
    lines.append(r"\midrule")

    lines.append(rf"\multicolumn{{{len(comparisons)+1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} {E}")
    lines.append(r"\addlinespace[2pt]")
    for param in ("var3", "var5"):
        label = PARAM_LABELS_LATEX[param]
        row_cells = [fmt_cell(float(data[cmp]["IV"][param].coef), float(data[cmp]["IV"][param].se), float(data[cmp]["IV"][param].pval)) for cmp in comparisons]  # type: ignore[index]
        lines.append(f"{indent}{label} & " + " & ".join(row_cells) + f" {E}")
    lines.append(r"\midrule")
    rkfs = [data[c]["rkf"] for c in comparisons]
    lines.append("KP rk Wald F & " + " & ".join(f"{v:.2f}" if v is not None else "--" for v in rkfs) + f" {E}")
    lines.append("N & " + " & ".join(f"{data[c]['nobs']:,}" for c in comparisons) + f" {E}")
    lines.append(r"\midrule")

    blanks = " & ".join(["" for _ in comparisons])
    lines.append(f"\\textbf{{Fixed Effects}} & {blanks} {E}")

    lines.append(f"{indent}Time & " + " & ".join(["$\\checkmark$"] * len(comparisons)) + f" {E}")
    lines.append(
        f"{indent}Firm & "
        + " & ".join("$\\checkmark$" if data[c]["fe_tag"] == "regular" else "" for c in comparisons)
        + f" {E}"
    )
    lines.append(
        f"{indent}Individual & "
        + " & ".join("$\\checkmark$" if data[c]["fe_tag"] == "regular" else "" for c in comparisons)
        + f" {E}"
    )
    lines.append(
        f"{indent}Firm $\\times$ Individual & "
        + " & ".join("$\\checkmark$" if data[c]["fe_tag"] == "match" else "" for c in comparisons)
        + f" {E}"
    )
    lines.append(r"\midrule")

    lines.append(f"\\textbf{{Comparison Group}} & {blanks} {E}")
    lines.append(
        f"{indent}Hybrid & "
        + " & ".join("$\\checkmark$" if COMPARISON_COLUMNS[c]["group"] == "Hybrid" else "" for c in comparisons)
        + f" {E}"
    )
    lines.append(
        f"{indent}Hybrid/In-Person & "
        + " & ".join(
            "$\\checkmark$" if COMPARISON_COLUMNS[c]["group"] == "Hybrid/In-Person" else "" for c in comparisons
        )
        + f" {E}"
    )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create fully-remote comparison table")
    parser.add_argument("--variant", default="precovid", help="Panel variant (default: precovid)")
    parser.add_argument(
        "--comparisons",
        default=",".join(COMPARISON_COLUMNS.keys()),
        help="Comma-separated column keys to include (default: all)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional override for output path under results/final/tex",
    )
    args = parser.parse_args()

    comps = [c.strip() for c in args.comparisons.split(",") if c.strip()]
    for cmp in comps:
        if cmp not in COMPARISON_COLUMNS:
            raise ValueError(f"Unknown comparison '{cmp}'")

    table = build_table(args.variant, comps)

    FINAL_TEX_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = FINAL_TEX_DIR / out_path
    else:
        out_path = FINAL_TEX_DIR / f"user_productivity_fr_focus_{args.variant}.tex"
    out_path.write_text(table)

    print(f"Wrote table to {out_path}")


if __name__ == "__main__":
    main()
