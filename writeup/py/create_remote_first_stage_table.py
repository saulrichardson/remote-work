#!/usr/bin/env python3
"""Generate LaTeX table for a simple first‐stage regression of *Remote* on
Teleworkable.

The source file ``results/raw/firm_remote_first_stage/first_stage.csv`` holds
one row with columns:

    endovar,param,coef,se,pval,partialF,rkf,nobs

We convert that into a small one–column table similar in look to the other
first‐stage tables included in the consolidated PDF.  Because only one
endogenous variable is present, Kleibergen–Paap statistics and FE indicator
rows are omitted.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

RAW_CSV = PROJECT_ROOT / "results" / "raw" / "firm_remote_first_stage" / "first_stage.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / "remote_first_stage.tex"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    r"""Return a centred ``\makecell`` with coefficient and (se)."""
    return rf"\makecell[c]{{{coef:.3f}{stars(p)}\\({se:.3f})}}"


# ---------------------------------------------------------------------------
# Load CSV
# ---------------------------------------------------------------------------

if not RAW_CSV.exists():
    raise FileNotFoundError(RAW_CSV)

df = pd.read_csv(RAW_CSV)

# Expect exactly one endogenous variable; take the first.
ENDO = df["endovar"].iloc[0]

# Human-readable labels -------------------------------------------------------

COL_LABEL = {
    "remote": r"$ \text{Remote} $",
}

PARAM_LABEL = {
    "teleworkable": r"$ \text{Teleworkable} $",
}


# ---------------------------------------------------------------------------
# Build LaTeX lines
# ---------------------------------------------------------------------------

lines: list[str] = []

lines.append(r"% Auto-generated – Remote on Teleworkable first stage")
lines.append(r"\begin{table}[H]")
lines.append(r"\centering")
lines.append(r"\caption{First-Stage Estimate: Remote $\rightarrow$ Teleworkable}")
lines.append(r"\label{tab:remote_first_stage}")

# Preamble
lines.append(r"\begin{tabular}{lc}")
lines.append(r"\toprule")
lines.append(rf" & {COL_LABEL.get(ENDO, ENDO)}\\")
lines.append(r"\midrule")

# Coefficient row
row = df.iloc[0]
coef_cell = cell(row.coef, row.se, row.pval)
lines.append(rf"{PARAM_LABEL.get(row.param, row.param)} & {coef_cell}\\")

lines.append(r"\midrule")

# Summary statistics rows – include $R^{2}$ if present
# Add R^2 row when column present in CSV
if "r2" in df.columns and not pd.isna(row.get("r2")):
    lines.append(rf"$R^2$ & {float(row.r2):.3f}\\")

lines.append(rf"N & {int(row.nobs):,}\\")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")
