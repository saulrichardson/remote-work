#!/usr/bin/env python3
"""Create a LaTeX table summarising pairwise remote modality comparisons."""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

import math
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw"
CLEAN_DIR = PROJECT_ROOT / "results" / "cleaned"

COMPARISONS = OrderedDict(
    [
        (
            "fr_vs_ip",
            {
                "title": "Fully Remote vs In-Person",
                "short": "FR vs IP",
            },
        ),
        (
            "hyb_vs_ip",
            {
                "title": "Hybrid vs In-Person",
                "short": "H vs IP",
            },
        ),
        (
            "fr_vs_hyb",
            {
                "title": "Fully Remote vs Hybrid",
                "short": "FR vs H",
            },
        ),
    ]
)

PARAM_LABELS_LATEX = {
    "var3": r"$ \mathds{1}(\text{Treated}) \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \mathds{1}(\text{Treated}) \times \mathds{1}(\text{Post}) \times \text{Startup} $",
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
    return f"\\makecell[c]{{{coef:.2f}{stars(p)}\\\\({se:.2f})}}"


def load_comparison(variant: str, suffix: str) -> dict:
    base_dir = RAW_DIR / f"user_productivity_pairwise_{variant}_{suffix}"
    csv_path = base_dir / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing results for {variant}/{suffix}: {csv_path}")

    df = pd.read_csv(csv_path)
    var3_name = f"var3_{suffix}"
    var5_name = f"var5_{suffix}"

    out: dict[str, dict[str, pd.Series] | float | int | None] = {"OLS": {}, "IV": {}}
    for model in ("OLS", "IV"):
        sub = df[df["model_type"] == model]
        for param, name in (("var3", var3_name), ("var5", var5_name)):
            row = sub[sub["param"] == name]
            if row.empty:
                raise ValueError(f"Missing {name} for {suffix} ({model})")
            out[model][param] = row.iloc[0]

    any_ols = out["OLS"]["var3"]  # type: ignore[index]
    any_iv = out["IV"]["var3"]    # type: ignore[index]
    out["pre_mean"] = float(any_ols.pre_mean)
    out["nobs"] = int(any_ols.nobs)
    out["rkf"] = float(any_iv.rkf) if not math.isnan(any_iv.rkf) else None
    return out


def build_table(variant: str, comparisons: Iterable[str]) -> str:
    comparisons = list(comparisons)
    data = {cmp: load_comparison(variant, cmp) for cmp in comparisons}

    headers = [COMPARISONS[cmp]["short"].replace("&", "\\&") for cmp in comparisons]

    lines: list[str] = []
    lines.append("% Auto-generated: user productivity pairwise remote comparisons")
    colspec = "@{}l" + "@{\\extracolsep{\\fill}}c" * len(comparisons) + "@{}"
    lines.append(f"\\begin{{tabular*}}{{\\linewidth}}{{{colspec}}}")
    E = "\\\\"
    lines.append("\\toprule")
    lines.append("& " + " & ".join(headers) + f" {E}")
    lines.append("\\midrule")

    lines.append(f"\\multicolumn{{{len(comparisons)+1}}}{{@{{}}l}}{{\\textbf{{\\uline{{Panel A: OLS}}}}}} {E}")
    lines.append("\\addlinespace[2pt]")
    indent = r"\hspace{1em}"
    for param in ("var3", "var5"):
        label = PARAM_LABELS_LATEX[param]
        row = [f"{indent}{label}"]
        for cmp in comparisons:
            s = data[cmp]["OLS"][param]  # type: ignore[index]
            row.append(fmt_cell(float(s.coef), float(s.se), float(s.pval)))
        lines.append(" & ".join(row) + f" {E}")
    lines.append("\\midrule")
    lines.append("Pre-Covid Mean & " + " & ".join(f"{data[c]['pre_mean']:.2f}" for c in comparisons) + f" {E}")
    lines.append("N & " + " & ".join(f"{data[c]['nobs']:,}" for c in comparisons) + f" {E}")
    lines.append("\\midrule")

    lines.append(f"\\multicolumn{{{len(comparisons)+1}}}{{@{{}}l}}{{\\textbf{{\\uline{{Panel B: IV}}}}}} {E}")
    lines.append("\\addlinespace[2pt]")
    for param in ("var3", "var5"):
        label = PARAM_LABELS_LATEX[param]
        row = [f"{indent}{label}"]
        for cmp in comparisons:
            s = data[cmp]["IV"][param]  # type: ignore[index]
            row.append(fmt_cell(float(s.coef), float(s.se), float(s.pval)))
        lines.append(" & ".join(row) + f" {E}")
    lines.append("\\midrule")
    rkfs = [data[c]["rkf"] for c in comparisons]
    lines.append(
        "KP rk Wald F & "
        + " & ".join(f"{v:.2f}" if v is not None else "--" for v in rkfs)
        + f" {E}"
    )
    lines.append("N & " + " & ".join(f"{data[c]['nobs']:,}" for c in comparisons) + f" {E}")
    lines.append("\\midrule")

    blanks = " & ".join(["" for _ in comparisons])
    lines.append("\\textbf{Fixed Effects} & " + blanks + f" {E}")
    lines.append(f"{indent}Time & " + " & ".join(["$\\checkmark$"] * len(comparisons)) + f" {E}")
    lines.append(f"{indent}Firm $\\times$ Individual FE & " + " & ".join(["$\\checkmark$"] * len(comparisons)) + f" {E}")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular*}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create pairwise remote modality table")
    parser.add_argument("--variant", default="precovid", help="Panel variant (default: precovid)")
    parser.add_argument(
        "--comparisons",
        default=",".join(COMPARISONS.keys()),
        help="Comma-separated comparison suffixes to include (default: all)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional override for output path under results/final/tex",
    )
    args = parser.parse_args()

    comps = [c.strip() for c in args.comparisons.split(",") if c.strip()]
    for cmp in comps:
        if cmp not in COMPARISONS:
            raise ValueError(f"Unknown comparison '{cmp}'")

    table = build_table(args.variant, comps)

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = CLEAN_DIR / out_path
    else:
        out_path = CLEAN_DIR / f"user_productivity_pairwise_{args.variant}.tex"
    out_path.write_text(table)

    print(f"Wrote table to {out_path}")


if __name__ == "__main__":
    main()
