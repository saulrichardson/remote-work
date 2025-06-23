#!/usr/bin/env python3
"""Create two separate LaTeX tables (OLS and IV) from a consolidated CSV.

Compared to *simple_table_from_consolidated.py* this variant

1. produces **one file per model type** (suffix ``_ols`` / ``_iv``), and
2. appends the usual summary statistics rows – currently
   • *N*         – taken from the ``nobs`` column
   • *KP rk Wald F* (first-stage strength) – from the ``rkf`` column (IV only).

The basic visual style (booktabs + makecell) remains the same, but each table
has a single numeric column instead of two side-by-side.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

import pandas as pd

# ---------------------------------------------------------------------------
# Shared helpers from the single-table script (imported directly) -------------
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
SIMPLE_PATH = HERE / "simple_table_from_consolidated.py"

# To avoid code duplication we import the helper module and reuse its
# DEFAULT_PARAM_LABEL, stars(), make_cell() functions.

import importlib.util

spec = importlib.util.spec_from_file_location("_simple", SIMPLE_PATH)
# load helper module
simple = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec is not None and spec.loader is not None
spec.loader.exec_module(simple)  # type: ignore[assignment]

# Re-export for convenience
DEFAULT_PARAM_LABEL = simple.DEFAULT_PARAM_LABEL
stars = simple.stars
make_cell = simple.make_cell
canonical_param = simple.canonical_param
pretty_label = simple.pretty_label


# ---------------------------------------------------------------------------
# Core table builder (one model at a time) -----------------------------------
# ---------------------------------------------------------------------------


def build_single_model(df: pd.DataFrame, *, model: str, caption: str, label: str) -> str:
    """Return LaTeX for *model* ("OLS" or "IV")."""

    if df.empty:
        raise ValueError("Empty data frame passed to build_single_model")

    # Order parameters: the known three first, then any extras
    uniq = list(df["param"].unique())

    def sort_key(p: str) -> tuple[int, str]:
        base = canonical_param(p)
        if base == "var3":
            g = 0
        elif base == "var5":
            g = 1
        elif base == "var4":
            g = 2
        else:
            g = 3
        return (g, p)

    param_order = sorted(uniq, key=sort_key)

    rows: list[str] = []
    for param in param_order:
        sub = df.query("param == @param")
        if sub.empty:
            continue
        coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
        rows.append(
            " & ".join([
                pretty_label(param).strip(),
                make_cell(coef, se, pval),
            ])
            + r" \\"  # terminate row
        )

    # Summary stats ---------------------------------------------------------
    nobs = int(df["nobs"].dropna().iloc[0]) if "nobs" in df.columns else None
    rkf = df["rkf"].dropna().iloc[0] if "rkf" in df.columns and model == "IV" else None

    rows.append(r"\midrule")
    if nobs is not None:
        rows.append(f"N & {nobs:,} " + r" \\")
    if rkf is not None:
        rows.append(f"KP rk Wald F & {rkf:.2f} " + r" \\")

    body = "\n".join(rows)

    header = "Parameter & " + model + r" \\"  # header row

    tex_content = f"""% Auto-generated from consolidated_results.csv
\\begin{{table}}[H]
\\caption{{{caption}}}
\\label{{{label}}}
\\centering
\\begin{{tabular}}{{ll}}
\\toprule
{header}
\\midrule
{body}
\\bottomrule
\\end{{tabular}}
\\end{{table}}"""

    tex = tex_content.strip()

    return tex + "\n"


# ---------------------------------------------------------------------------
# CLI ------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Split consolidated regression output into separate OLS and IV tables")
    p.add_argument("spec_dir", type=Path, help="Directory containing consolidated_results.csv")
    args = p.parse_args(argv)

    spec_dir: Path = args.spec_dir.expanduser().resolve()
    csv_path = spec_dir / "consolidated_results.csv"
    if not csv_path.exists():
        sys.exit(f"Error: {csv_path} not found")

    df = pd.read_csv(csv_path)

    spec_name = spec_dir.name  # base name

    out_root = spec_dir.parents[1] / "cleaned"
    out_root.mkdir(parents=True, exist_ok=True)

    for model in ["OLS", "IV"]:
        if model not in df["model_type"].unique():
            continue
        sub = df.query("model_type == @model")
        caption = f"{spec_name.replace('_', ' ').title()} – {model}"
        label = f"tab:{spec_name}_{model.lower()}"
        tex = build_single_model(sub, model=model, caption=caption, label=label)
        out_path = out_root / f"{spec_name}_{model.lower()}.tex"
        out_path.write_text(tex)
        try:
            rel = out_path.relative_to(Path.cwd())
        except ValueError:
            rel = out_path
        print(f"✓ Wrote {rel}")


if __name__ == "__main__":
    main()
