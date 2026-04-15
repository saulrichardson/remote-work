#!/usr/bin/env python3
"""Format Crunchbase last-VC-round recency bins into a compact LaTeX table.

This table is a meeting-style diagnostic: it answers "how recently have firms in
our matched sample raised VC funding?" using the raw Crunchbase funding rounds
export, summarized as-of a reference date.

Reads:
  results/raw/crunchbase_funding_recency/matched_private/last_vc_round_bins_summary.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_vc_recency.tex
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
SCRIPTS_DIR = HERE.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
from user_productivity.build_baseline_table import PREAMBLE_FLEX, TOP, MID, BOTTOM  # type: ignore


LB = r" \\"

DEFAULT_IN = (
    RESULTS_RAW
    / "crunchbase_funding_recency"
    / "matched_private"
    / "last_vc_round_bins_summary.csv"
)
DEFAULT_OUT = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_vc_recency.tex"


def column_format_padded(n_numeric: int) -> str:
    return "l" + (r"@{\extracolsep{\fill}}c" * n_numeric)


def fmt_cell(n: int | float | None, share: float | None) -> str:
    if n is None or share is None or pd.isna(n) or pd.isna(share):
        return "--"
    return f"{int(n):,} ({float(share):.3f})"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_IN, help="Input CSV path.")
    p.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Output TeX path.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(
            f"Missing VC recency summary: {args.input}. "
            "Build via: python src/py/build_crunchbase_last_vc_round.py --sample matched_private --asof 2020-01-01"
        )

    df = pd.read_csv(args.input)
    required = {"recency_bin", "n_firms", "definition", "share"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {args.input}.")

    # Keep keys aligned with the CSV output (which uses unicode "≤"), but render
    # labels using TeX-safe math symbols to avoid PDFLaTeX unicode pitfalls.
    ordered_bins: list[tuple[str, str]] = [
        ("never", "never"),
        ("≤2y", r"$\leq$2y"),
        ("≤5y", r"$\leq$5y"),
        ("≤10y", r"$\leq$10y"),
        (">10y", r"$>$10y"),
    ]

    # Pivot to definition columns.
    core = df[df["definition"] == "vc_core"].set_index("recency_bin")
    broad = df[df["definition"] == "vc_broad"].set_index("recency_bin")

    headers = ["Recency bin", "VC core", "VC broad"]

    lines: list[str] = [
        PREAMBLE_FLEX + r"\small" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(headers) - 1)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
    ]

    for key, label in ordered_bins:
        n_core = core.loc[key, "n_firms"] if key in core.index else None
        s_core = core.loc[key, "share"] if key in core.index else None
        n_broad = broad.loc[key, "n_firms"] if key in broad.index else None
        s_broad = broad.loc[key, "share"] if key in broad.index else None
        lines.append(" & ".join([label, fmt_cell(n_core, s_core), fmt_cell(n_broad, s_broad)]) + LB)

    lines.extend([BOTTOM, r"\end{tabular*}"])

    ensure_dir(args.output.parent)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote VC recency table → {args.output}")


if __name__ == "__main__":
    main()
