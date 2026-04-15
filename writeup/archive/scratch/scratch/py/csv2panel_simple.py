#!/usr/bin/env python3
"""
csv2panel_simple.py

Convert a consolidated_results.csv for total_contributions_q100 into a 2-column
LaTeX table of OLS vs IV coefficients (with standard errors). Works for any
user_productivity or firm_scaling consolidated CSV.
"""
from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path

def main() -> None:
    p = argparse.ArgumentParser(
        description="Simple one-panel LaTeX table (OLS vs IV) from consolidated CSV"
    )
    p.add_argument("-i", "--input", type=Path, required=True,
                   help="Path to consolidated_results.csv")
    p.add_argument("-o", "--output", type=Path, required=True,
                   help="Output .tex filename")
    p.add_argument("--caption", type=str, default=None,
                   help="LaTeX \caption text")
    p.add_argument("--label", type=str, default=None,
                   help="LaTeX \label text")
    args = p.parse_args()

    if not args.input.exists():
        p.error(f"Input not found: {args.input}")

    # Read and filter for the main outcome
    df = pd.read_csv(args.input)
    df = df[df["outcome"] == "total_contributions_q100"]

    # Format coef (se) strings
    df["coef_se"] = df.apply(lambda r: f"{r.coef:.3f} ({r.se:.3f})", axis=1)

    # Pivot model_type -> columns
    table = df.pivot(index="param", columns="model_type", values="coef_se").reset_index()
    table.columns.name = None
    table = table.rename(columns={"param": "Parameter"})

    # Build LaTeX
    lines: list[str] = []
    lines.append(f"% Auto-generated table from {args.input.name}")
    lines.append("\\begin{table}[H]")
    if args.caption:
        lines.append(f"\\caption{{{args.caption}}}")
    if args.label:
        lines.append(f"\\label{{{args.label}}}")
    lines.append("\\centering")
    # to_latex will escape underscores
    lines.append(table.to_latex(index=False, escape=True))
    lines.append("\\end{table}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    print(f"Wrote LaTeX table to {args.output}")

if __name__ == "__main__":
    main()