#!/usr/bin/env python3
"""Build a compact LaTeX table from *heterogeneity* CSV files produced by the
Stata scripts *user_productivity_…_base*.  Unlike the *consolidated* results
the heterogeneity output holds **one row per *bucket*** (0 / 1 / 2, …) and
stores the statistics for the endogenous parameters in distinct columns::

    bucket,coef3,se3,pval3,coef5,se5,pval5,rkf,nobs

The goal is a clean *booktabs* table where **each bucket is a separate column**
and the **rows are the parameters** (var3, var5, var4, …).  The script is
robust to any number of buckets – the header and column specification are
constructed dynamically.

Usage
-----
    python py/heterogeneity_table.py /path/to/var5_modal_base.csv

Optional flags allow custom caption/label and destination directory.  The
output mirrors the behaviour of *simple_table_from_consolidated.py* and is
written to *results/final/tex/<csv-stem>.tex* by default.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Re-use helpers (pretty labels, significance stars, make_cell) -------------
# ---------------------------------------------------------------------------

SIMPLE_PATH = HERE / "simple_table_from_consolidated.py"

import importlib.util

spec = importlib.util.spec_from_file_location("_simple", SIMPLE_PATH)
_simple = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec is not None and spec.loader is not None
spec.loader.exec_module(_simple)  # type: ignore[arg-type]

pretty_label = _simple.pretty_label  # type: ignore[attr-defined]
stars = _simple.stars  # type: ignore[attr-defined]


def make_cell(coef: float, se: float, p: float, decimals: int = 3) -> str:  # noqa: D401
    """Return a centred ``\\makecell`` with coefficient, stars and SE."""

    return rf"\makecell[c]{{{coef:.{decimals}f}{stars(p)}\\({se:.{decimals}f})}}"


# ---------------------------------------------------------------------------
# Infer *parameters* present in a heterogeneity CSV -------------------------
# ---------------------------------------------------------------------------


def detect_parameters(columns: List[str]) -> Dict[str, dict]:
    """Return mapping **param → column triple** for every var present.

    The CSV columns follow the pattern ``coefX`` / ``seX`` / ``pvalX`` where
    *X* is a number that maps to the Stata parameter ``varX``.
    """

    # Collect trailing numbers that appear in *all* three column types
    found: Dict[str, dict] = {}
    for col in columns:
        m = re.match(r"coef(\d+)$", col)
        if m:
            num = m.group(1)
            se_col = f"se{num}"
            p_col = f"pval{num}"
            if se_col in columns and p_col in columns:
                found[f"var{num}"] = {"coef": col, "se": se_col, "pval": p_col}

    return found


# ---------------------------------------------------------------------------
# Core builder --------------------------------------------------------------
# ---------------------------------------------------------------------------


def build_table(
    df: pd.DataFrame,
    *,
    caption: str,
    label: str,
    bucket_labels: list[str] | None = None,
) -> str:
    """Return LaTeX table string with *buckets as columns* and *parameters as rows*."""

    buckets = sorted(df["bucket"].unique())

    param_cols = detect_parameters(df.columns.tolist())
    if not param_cols:
        raise ValueError("No coef*/se*/pval* column triples found – not a supported heterogeneity CSV.")

    # Order parameters: var3, var5, var4, rest (same ordering logic as elsewhere)
    def sort_key(p: str):
        if p == "var3":
            g = 0
        elif p == "var5":
            g = 1
        elif p == "var4":
            g = 2
        else:
            g = 3
        return (g, p)

    param_order = sorted(param_cols.keys(), key=sort_key)

    # Build rows -----------------------------------------------------------
    body_rows: List[str] = []
    for param in param_order:
        cols: List[str] = [pretty_label(param).strip()]
        triple = param_cols[param]
        for b in buckets:
            sub = df[df["bucket"] == b]
            if sub.empty:
                cols.append("")
                continue
            coef, se, pval = sub.iloc[0][[triple["coef"], triple["se"], triple["pval"]]]
            cols.append(make_cell(float(coef), float(se), float(pval)))
        # terminate each row – needs *double* backslash in final TeX, hence
        # four in a normal Python string (escaped twice) or two inside a raw
        # string.
        body_rows.append(" & ".join(cols) + r" \\")

    # Summary statistics ---------------------------------------------------
    stats_rows: List[str] = []

    # N (nobs) per bucket ---------------------------------------------------
    nobs_vals = [int(df.query("bucket == @b")["nobs"].iloc[0]) for b in buckets]
    stats_rows.append("N & " + " & ".join(f"{v:,}" for v in nobs_vals) + r" \\")

    # KP rk Wald F per bucket ----------------------------------------------
    if "rkf" in df.columns:
        rkf_series = [df.query("bucket == @b")["rkf"].iloc[0] for b in buckets]
        # If all values are missing/NaN (e.g., OLS), skip the row entirely
        import math
        if not all((v is None) or (isinstance(v, float) and math.isnan(v)) for v in rkf_series):
            def fmt_rkf(v: float) -> str:
                try:
                    if isinstance(v, float) and math.isnan(v):
                        return ""
                    return f"{float(v):.2f}"
                except Exception:
                    return ""
            stats_rows.append("KP rk Wald F & " + " & ".join(fmt_rkf(v) for v in rkf_series) + r" \\")

    # Assemble LaTeX -------------------------------------------------------
    # Optional override for bucket labels (must match number of buckets)
    labels = [str(b) for b in buckets]
    if bucket_labels and len(bucket_labels) == len(buckets):
        labels = bucket_labels
    header_cols = ["Parameter", *labels]
    header = " & ".join(header_cols) + r" \\"

    body = "\n".join(body_rows + [r"\midrule"] + stats_rows)

    # Left-align the parameter column, centre the numeric ones.
    col_spec = "l" + "c" * (len(header_cols) - 1)

    tex_lines = [
        "% Auto-generated heterogeneity table",
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

    return "\n".join(tex_lines) + "\n"


# ---------------------------------------------------------------------------
# CLI -----------------------------------------------------------------------
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate LaTeX table from heterogeneity CSV (bucket columns)")
    p.add_argument("csv_path", type=Path, help="CSV file produced by Stata heterogeneity script")
    p.add_argument("--caption", help="Custom caption (defaults to derived from file name)")
    p.add_argument("--label", help="Custom LaTeX label (defaults to derived from file name)")
    p.add_argument("--out", type=Path, help="Output .tex file (defaults to results/final/tex/<stem>.tex)")
    p.add_argument(
        "--bucket-labels",
        help="Comma-separated labels for buckets in sorted order (e.g., 'Outside,Inside,Remote')",
    )
    args = p.parse_args(argv)

    csv_path: Path = args.csv_path.expanduser().resolve()
    if not csv_path.exists():
        sys.exit(f"Error: {csv_path} not found")

    df = pd.read_csv(csv_path)

    stem = csv_path.stem  # e.g. var5_modal_base
    caption = args.caption or stem.replace("_", " ").title()
    label = args.label or f"tab:{stem}"

    blist: list[str] | None = None
    if args.bucket_labels:
        blist = [s.strip() for s in args.bucket_labels.split(",")]
    tex_str = build_table(df, caption=caption, label=label, bucket_labels=blist)

    if args.out is not None:
        out_path = args.out.expanduser().resolve()
    else:
        # results/final/tex/<stem>.tex  – stay consistent with other helpers
        out_path = csv_path.parents[2] / "cleaned" / f"{stem}.tex"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex_str)
    try:
        rel = out_path.relative_to(Path.cwd())
    except ValueError:
        rel = out_path
    print(f"✓ Wrote {rel}")


if __name__ == "__main__":
    main()
