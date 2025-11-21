#!/usr/bin/env python3
"""Create compact drop/keep CSA tables with both FE variants (Std vs firm×user)."""

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
from build_top_metro_dualfe_table import (  # type: ignore
    build_columns,
    build_table,
    load_results,
)

SCENARIOS: dict[str, list[tuple[str, str]]] = {
    "drop": [
        ("precovid_droptop5", "Drop Top 5 CSAs"),
        ("precovid_droptop10", "Drop Top 10 CSAs"),
    ],
    "keep": [
        ("precovid_keeptop5", "Keep Top 5 CSAs"),
        ("precovid_keeptop10", "Keep Top 10 CSAs"),
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
        help="Destination TeX file (defaults to results/cleaned/tex/user_productivity_<scenario>_top_metros_dualfe_two_col.tex).",
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
    df = load_results(args.results_root, variants)
    columns = build_columns(variants)
    label_map = dict(variants)

    output_path = args.output
    if output_path is None:
        output_path = RESULTS_CLEANED_TEX / f"user_productivity_{args.scenario}_top_metros_dualfe_two_col.tex"
    ensure_dir(output_path.parent)

    tex = build_table(df, columns=columns, outcome=args.outcome, label_map=label_map)
    output_path.write_text(tex)
    print(f"Wrote two-column dual-FE {args.scenario} table → {output_path}")


if __name__ == "__main__":
    main()
