#!/usr/bin/env python3
"""Build compact drop/keep CSA tables (top 5 vs top 10 only) for the mini-writeup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
from build_top_metro_drop_table import combine_variants, build_table  # type: ignore

SCENARIOS: dict[str, list[tuple[str, str]]] = {
    "drop": [
        ("precovid_droptop5", "Drop CSAs Ranked 1–5"),
        ("precovid_droptop14", "Drop CSAs Ranked 1–14"),
    ],
    "keep": [
        ("precovid_keeptop5", "Keep CSAs Ranked 1–5"),
        ("precovid_keeptop6_14", "Keep CSAs Ranked 6–14"),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-root",
        type=Path,
        default=RESULTS_RAW,
        help="Base directory containing the spec result folders.",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS.keys()),
        default="drop",
        help="Which CSA scenario to use (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination TeX file (defaults to results/cleaned/tex/user_productivity_<scenario>_top_metros_two_col.tex).",
    )
    parser.add_argument(
        "--outcome",
        default="total_contributions_q100",
        help="Outcome to display (default: total_contributions_q100).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    variants = SCENARIOS[args.scenario]
    df, columns = combine_variants(results_root=args.results_root, entries=variants)

    output_path = args.output
    if output_path is None:
        output_path = RESULTS_CLEANED_TEX / f"user_productivity_{args.scenario}_top_metros_two_col.tex"
    ensure_dir(output_path.parent)

    tex = build_table(df=df, columns=columns, outcome=args.outcome)
    output_path.write_text(tex)
    print(f"Wrote two-column {args.scenario} top-CSA table → {output_path}")


if __name__ == "__main__":
    main()
