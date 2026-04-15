#!/usr/bin/env python3
"""
Generate OLS + IV tables for the expanded FE variants of the user-productivity
spec, without touching existing outputs or whitelists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW  # type: ignore
from build_baseline_table import PREAMBLE_FLEX, build_panel_fe  # type: ignore

DEFAULT_FE_TAGS = [
    "firmyear_match",   # absorb(firm × year, firm × user, yh)
    "firmyear",         # absorb(firm × year, yh)
    "indyear_match",    # absorb(industry × year, firm × user, yh)
    "indyear",          # absorb(industry × year, yh)
]


def load_results(variant: str) -> pd.DataFrame:
    path = RESULTS_RAW / f"user_productivity_fe_expanded_{variant}" / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing consolidated results at {path}")
    return pd.read_csv(path)


def write_table(
    df: pd.DataFrame,
    *,
    model: str,
    columns: list[tuple[str, str]],
    headers: dict[str, str],
    output_path: Path,
) -> None:
    table_body = build_panel_fe(
        df,
        model=model,
        include_kp=(model.upper() == "IV"),
        columns=columns,
        headers=headers,
        panel_label=None,
    ).rstrip()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(PREAMBLE_FLEX + table_body + "\n")
    print(f"Wrote {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build OLS/IV tables for expanded FE variants (user productivity)."
    )
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="Panel variant to load (default: %(default)s)",
    )
    parser.add_argument(
        "--fe-tags",
        nargs="+",
        default=DEFAULT_FE_TAGS,
        help="FE tags to include as columns (default: %(default)s)",
    )
    parser.add_argument(
        "--outcome",
        default="total_contributions_q100",
        help="Outcome column to tabulate (default: %(default)s)",
    )
    parser.add_argument(
        "--header",
        default="Contribution Rank",
        help="Column header label for the selected outcome (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = load_results(args.variant)
    df = df[df["fe_tag"].isin(args.fe_tags)]
    if df.empty:
        raise RuntimeError(f"No rows found for FE tags {args.fe_tags}")

    columns = [(args.outcome, tag) for tag in args.fe_tags]
    headers = {args.outcome: args.header}

    base = f"user_productivity_{args.variant}_fe_expanded"
    out_ols = RESULTS_CLEANED_TEX / f"{base}_ols.tex"
    out_iv = RESULTS_CLEANED_TEX / f"{base}_iv.tex"

    write_table(df, model="OLS", columns=columns, headers=headers, output_path=out_ols)
    write_table(df, model="IV", columns=columns, headers=headers, output_path=out_iv)


if __name__ == "__main__":
    main()
