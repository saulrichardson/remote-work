#!/usr/bin/env python3
"""Create a compact LaTeX regression table from a single
``consolidated_results.csv`` file.

A *consolidated* CSV produced by the Stata/Julia pipelines typically has one
row per (model type × parameter) combination, with columns

    • model_type  – "OLS" / "IV" (capitalisation kept as-is)
    • outcome     – name of the dependent variable (ignored here)
    • param       – Stata internal parameter name (var3, var5, …)
    • coef, se, pval  – coefficient, robust SE, p-value

This helper script turns that into a minimal but nicely formatted booktabs
table that mirrors the look of the *tmp_*.tex placeholders already present in
results/final/tex/.

Usage
-----
python py/simple_table_from_consolidated.py \
       /path/to/spec_dir              # folder that *contains* consolidated_results.csv

Optional flags allow custom caption, label, output directory and variable
name mapping.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import dedent
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# Default pretty-print mapping for common Stata variable names
# ---------------------------------------------------------------------------

DEFAULT_PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# ---------------------------------------------------------------------------
# Helper to normalise Stata param names that carry a *variant* suffix such as
#   var3_fullrem   var5_hybrid   …
# We strip the suffix because the mathematical meaning of the coefficient is
# unchanged – only the *sample* differs.
# ---------------------------------------------------------------------------

import re


def canonical_param(p: str) -> str:
    """Return *base* name (var3, var4, var5, …) without any variant suffix."""

    m = re.match(r"(var\d+)(?:_.*)?", p)
    return m.group(1) if m else p


def pretty_label(p: str) -> str:
    """Human-readable label for parameter *p* (handles suffixed variants)."""

    base = canonical_param(p)
    return DEFAULT_PARAM_LABEL.get(base, p)

# Significance symbols -------------------------------------------------------

STAR_LEVELS: list[tuple[float, str]] = [
    (0.01, "***"),
    (0.05, "**"),
    (0.10, "*"),
]


def stars(p: float) -> str:
    """Return the usual ***, **, * significance stars for *p*."""

    for cut, sym in STAR_LEVELS:
        if p < cut:
            return sym
    return ""


def make_cell(coef: float, se: float, p: float, decimals: int = 3) -> str:
    """Format a coefficient + SE inside a centred ``\makecell``."""

    return rf"\makecell[c]{{{coef:.{decimals}f}{stars(p)}\\({se:.{decimals}f})}}"


# ---------------------------------------------------------------------------
# Core routine
# ---------------------------------------------------------------------------


def build_table(df: pd.DataFrame, *, caption: str, label: str) -> str:
    """Return a complete LaTeX table for *df*.  The table has two numeric
    columns: IV and OLS (in that order) and one text column for the
    parameter label.
    """

    # Ensure we have the expected model types; fall back gracefully.
    models = [m for m in ("IV", "OLS") if m in df["model_type"].unique()]
    if not models:
        raise ValueError("No recognised model types (IV/OLS) found in CSV.")

    # Sort parameters as in DEFAULT_PARAM_LABEL, then any remaining ones.
    uniq = list(df["param"].unique())

    def sort_key(p: str) -> tuple[int, str]:
        base = canonical_param(p)
        if base == "var3":
            group = 0
        elif base == "var5":
            group = 1
        elif base == "var4":
            group = 2
        else:
            group = 3
        return (group, p)

    param_order = sorted(uniq, key=sort_key)

    rows: list[str] = []
    for param in param_order:
        # Remove stray leading/trailing spaces – otherwise TeX may think there
        # is an *empty* column before/after the math expression and throw a
        # “Misplaced \noalign” error when the column counts no longer match.
        plabel_tex = pretty_label(param).strip()

        cells = [plabel_tex]
        for model in models:
            sub = df.query("param == @param and model_type == @model")
            if sub.empty:
                cells.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                cells.append(make_cell(coef, se, pval))
        # End each row with a *double* backslash – needs four in a normal
        # Python string or we end up emitting only a single one which breaks
        # alignment inside the tabular.
        rows.append(" & ".join(cells) + r" \\")

    body = "\n".join(rows)

    # Build LaTeX using booktabs, avoid blank lines inside tabular
    header_cols = ["Parameter", *models]
    header = " & ".join(header_cols) + r" \\"  # header row

    col_spec = "l" * len(header_cols)

    lines = [
        "% Auto-generated table from consolidated_results.csv",
        "\\begin{table}[H]",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        "\\centering",
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\toprule",
        header,
        "\\midrule",
        body,
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate quick LaTeX table from consolidated regression output")
    p.add_argument("spec_dir", type=Path, help="Directory containing consolidated_results.csv")
    p.add_argument("--caption", default=None, help="Custom table caption (defaults to derived spec name)")
    p.add_argument("--label",   default=None, help="Custom LaTeX label (defaults to derived spec name)")
    p.add_argument("--out",     type=Path, default=None, help="Destination .tex file (defaults to results/final/tex/<spec>.tex)")
    args = p.parse_args(argv)

    spec_dir: Path = args.spec_dir.expanduser().resolve()
    csv_path = spec_dir / "consolidated_results.csv"
    if not csv_path.exists():
        sys.exit(f"Error: {csv_path} not found")

    df = pd.read_csv(csv_path)

    spec_name = spec_dir.name  # e.g. user_productivity_precovid_weighted
    caption = args.caption or spec_name.replace("_", " ").title()
    label = args.label or f"tab:{spec_name}"

    tex_str = build_table(df, caption=caption, label=label)

    # Work out output location ------------------------------------------------
    out_path: Path
    if args.out is not None:
        out_path = args.out
    else:
        out_path = spec_dir.parents[1] / "final" / "tex" / f"{spec_name}.tex"  # results/final/tex/
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex_str)
    print(f"✓ Wrote {out_path.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
