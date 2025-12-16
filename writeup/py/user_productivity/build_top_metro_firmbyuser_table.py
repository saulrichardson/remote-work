#!/usr/bin/env python3
"""Compact CSA table (keep/drop × firm×user FE only)."""

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
    build_table,
    load_results,
)

COLUMN_ORDER: list[tuple[str, str]] = [
    ("precovid_keeptop5", "Keep CSAs Ranked 1–5"),
    ("precovid_keeptop10", "Keep CSAs Ranked 1–10"),
    ("precovid_droptop5", "Drop CSAs Ranked 1–5"),
    ("precovid_droptop10", "Drop CSAs Ranked 1–10"),
]


def build_columns() -> list[tuple[tuple[str, str], str]]:
    return [((variant, "firm"), label) for variant, label in COLUMN_ORDER]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-root",
        type=Path,
        default=RESULTS_RAW,
        help="Base directory containing the spec result folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination TeX file (defaults to results/cleaned/tex/user_productivity_top_metros_firmbyuser.tex).",
    )
    parser.add_argument(
        "--outcome",
        default="total_contributions_q100",
        help="Outcome to display (default: total_contributions_q100).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = load_results(args.results_root, COLUMN_ORDER)
    df = df.loc[df["fe_kind"] == "firm"].copy()
    columns = build_columns()
    label_map = dict(COLUMN_ORDER)

    output_path = args.output
    if output_path is None:
        output_path = RESULTS_CLEANED_TEX / "user_productivity_top_metros_firmbyuser.tex"
    ensure_dir(output_path.parent)

    tex = build_table(df, columns=columns, outcome=args.outcome, label_map=label_map)
    cleaned_lines = []
    skip_prefixes = (
        r"\hspace{1em}Firm &",
        r"\hspace{1em}Individual &",
    )
    for line in tex.splitlines():
        stripped = line.lstrip()
        if any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        cleaned_lines.append(line)
    tex = "\n".join(cleaned_lines)
    output_path.write_text(tex)
    print(f"Wrote firm×user CSA table → {output_path}")


if __name__ == "__main__":
    main()
