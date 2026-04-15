#!/usr/bin/env python3
"""
csv2panel_user.py

Read any consolidated_results.csv containing total_contributions_q100 results
and produce a single FE-horse-race table (Panel A) in existing style.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path

def load_user_builder() -> object:
    path = Path(__file__).resolve().parent / "create_user_productivity_table.py"
    spec = importlib.util.spec_from_file_location("uptab", path)
    uptab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uptab)
    return uptab

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate FE-panel user-productivity table from CSV"
    )
    parser.add_argument(
        "-i", "--input", type=Path, required=True,
        help="consolidated_results.csv path"
    )
    parser.add_argument(
        "-o", "--output", type=Path, required=True,
        help="Output .tex file"
    )
    parser.add_argument(
        "--model-type", choices=["ols", "iv"], default="ols",
        help="OLS or IV"
    )
    args = parser.parse_args()

    if not args.input.exists():
        parser.error(f"Input not found: {args.input}")

    # load existing builder to reuse styles
    uptab = load_user_builder()

    import pandas as pd
    df = pd.read_csv(args.input)
    # force all rows into Panel A (FE variants) by tagging 'init'
    df['fe_tag'] = 'init'

    model = 'IV' if args.model_type=='iv' else 'OLS'
    include_kp = model=='IV'

    panel = uptab.build_panel_fe(df, model, include_kp)
    tex_lines = [
        '% Auto-generated user productivity table',
        '',
        r'\begin{table}[H]',
        r'\centering',
        rf'\caption{{User Productivity -- {model}}}',
        rf'\label{{tab:user_productivity_{args.model_type}}}',
        r'\centering',
        panel.rstrip(),
        r'\end{table}',
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(tex_lines)+"\n")
    print(f"Wrote LaTeX table to {args.output}")

if __name__ == '__main__':
    main()