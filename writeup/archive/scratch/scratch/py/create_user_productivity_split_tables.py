#!/usr/bin/env python3
"""Produce separate OLS and IV user-productivity tables for the mini-report.

This mirrors the combined layout from ``create_user_productivity_table.py``
but writes two standalone LaTeX tables (one per model type) so the mini-report
can include them independently without Panel A / Panel B blocks.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import create_user_productivity_table as base

PROJECT_ROOT: Path = base.PROJECT_ROOT
RAW_DIR: Path = base.RAW_DIR
SPEC_BASE: str = base.SPEC_BASE
OUTCOME_SETS = base.OUTCOME_SETS
DEFAULT_VARIANT: str = base.DEFAULT_VARIANT


def load_results(variant: str) -> pd.DataFrame:
    """Load and merge the baseline and alternative-FE regressions."""
    dir_alt = f"{SPEC_BASE}_alternative_fe_{variant}"
    dir_init = f"{SPEC_BASE}_initial_{variant}"

    input_alt = RAW_DIR / dir_alt / "consolidated_results.csv"
    input_init = RAW_DIR / dir_init / "consolidated_results.csv"

    df_init = pd.read_csv(input_init).copy()
    df_init["fe_tag"] = "init"

    df_alt = pd.read_csv(input_alt).copy()
    if "fe_tag" not in df_alt.columns:
        raise SystemExit("Alternative FE results missing 'fe_tag' column")

    return pd.concat([df_init, df_alt], ignore_index=True, sort=False)


def build_table(df: pd.DataFrame, *, model: str, columns, headers, caption: str, label: str) -> str:
    include_kp = model.upper() == "IV"
    body = base.build_panel_fe(
        df,
        model=model.upper(),
        include_kp=include_kp,
        columns=columns,
        headers=headers,
    )
    lines = [
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        body,
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create separate OLS / IV user productivity tables")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default=DEFAULT_VARIANT,
        help="User panel variant (default: %(default)s)",
    )
    parser.add_argument(
        "--outcome-set",
        choices=list(OUTCOME_SETS.keys()),
        default="total",
        help="Outcome bundle to render (default: %(default)s)",
    )
    args = parser.parse_args()

    df = load_results(args.variant)
    config = OUTCOME_SETS[args.outcome_set]
    columns = config["columns"]
    headers = config["headers"]

    out_dir = PROJECT_ROOT / "results" / "cleaned"
    out_dir.mkdir(parents=True, exist_ok=True)

    for model in ("OLS", "IV"):
        caption = f"User Productivity ({model})"
        if config["caption_suffix"]:
            caption = f"{caption}{config['caption_suffix']}"
        label = f"tab:{SPEC_BASE}_{args.variant}_{model.lower()}"
        if config["label_suffix"]:
            label = f"{label}{config['label_suffix']}"
        table_tex = build_table(
            df,
            model=model,
            columns=columns,
            headers=headers,
            caption=caption,
            label=label,
        )
        out_path = out_dir / f"{SPEC_BASE}_{args.variant}_{model.lower()}{config['filename_suffix']}.tex"
        out_path.write_text(table_tex)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
