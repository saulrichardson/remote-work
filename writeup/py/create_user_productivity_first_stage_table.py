#!/usr/bin/env python3
r"""Generate a LaTeX table summarising the **first-stage** regressions for the
base *User-Productivity* IV specification (i.e. *not* the alternative FE
variant).

Data source
-----------
results/raw/user_productivity/first_stage.csv – one row per instrument×endovar

Table layout
------------
Two endogenous variables (``var3`` and ``var5``) form the columns, while each
instrument (``param``) forms a row.  Within a cell the coefficient and its
robust standard error are stacked using ``\makecell``.  A short block of
summary statistics (partial F, KP rk Wald F, N) follows the coefficients.
"""

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "user_productivity"
INPUT_CSV = PROJECT_ROOT / "results" / "raw" / SPEC / "first_stage.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_first_stage.tex"

# ---------------------------------------------------------------------------
# Helper formatting utilities
# ---------------------------------------------------------------------------

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    r"""Return a centred ``\makecell`` holding *coef* and *(se)* with stars."""
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

if not INPUT_CSV.exists():
    raise FileNotFoundError(INPUT_CSV)

df = pd.read_csv(INPUT_CSV)

ENDOVARS = ["var3", "var5"]                      # column order

# ------------------------------------------------------------------
# Human-readable labels (shared with other table scripts)
# ------------------------------------------------------------------

COL_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

PARAM_LABEL = {
    "var6": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) $",
    "var7": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

PARAMS   = list(df["param"].unique())             # preserve CSV order

# ---------------------------------------------------------------------------
# Build LaTeX document
# ---------------------------------------------------------------------------

lines: list[str] = []

lines.append("% Auto-generated – do *not* edit by hand")
lines.append(r"\begin{table}[H]")
lines.append(r"\centering")
lines.append(r"\caption{First-Stage Estimates -- User Productivity}")
lines.append(r"\label{tab:user_productivity_first_stage}")

# Tabular preamble
col_spec = "l" + "c" * len(ENDOVARS)
lines.append(rf"\begin{{tabular}}{{{col_spec}}}")
lines.append(r"\toprule")
lines.append(r" & \multicolumn{2}{c}{Dependent variable}\\")
lines.append(r"\cmidrule(lr){2-3}")
# Header with descriptive column labels
header_cells = ["Instrument"] + [COL_LABEL.get(c, c) for c in ENDOVARS]
lines.append(" & ".join(header_cells) + r"\\")
lines.append(r"\midrule")

# Coefficient block
for param in PARAMS:
    row_cells = [PARAM_LABEL.get(param, param)]
    for endo in ENDOVARS:
        sub = df.query("param == @param and endovar == @endo")
        if sub.empty:
            row_cells.append("")
        else:
            row_cells.append(cell(*sub.iloc[0][["coef", "se", "pval"]]))

    lines.append(" & ".join(row_cells) + r"\\")

# ---------------------------------------------------------------
# FE indicator rows
# ---------------------------------------------------------------
lines.append(r"\midrule")

# Baseline spec has User, Firm, Time FE all included
fe_labels = [
    ("Time FE", True),
    ("Firm FE", True),
    ("User FE", True),
]

for lab, inc in fe_labels:
    marks = ["$\\checkmark$" if inc else "" for _ in ENDOVARS]
    lines.append(" & ".join([lab] + marks) + r"\\")

lines.append(r"\midrule")


# ---------------------------------------------------------------------------
# Summary rows (identical within endovar)
# ---------------------------------------------------------------------------


def first_val(col: str, endo: str):
    sub = df[df.endovar == endo].head(1)
    return sub.iloc[0][col] if not sub.empty else float("nan")

summary = {
    "Partial F": [first_val("partialF", e) for e in ENDOVARS],
    "N":         [int(first_val("nobs", e)) for e in ENDOVARS],
}

for label, vals in summary.items():
    formatted = [f"{v:.2f}" if isinstance(v, float) else f"{v:,}" for v in vals]
    lines.append(" & ".join([label] + formatted) + r"\\")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

# ---------------------------------------------------------------------------
# Write file
# ---------------------------------------------------------------------------
OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")
