#!/usr/bin/env python3
"""Generate a LaTeX table of the *first-stage* regressions for the **Firm-Scaling**
specification (base results, not the alternative-FE spec).

The source CSV lives under ``results/raw/firm_scaling/first_stage.csv`` and
contains one row per *instrument* (``param``) × *endogenous variable*
(``endovar``).

The script collapses the file into a 2-column table where each column is one
endogenous variable and each row is an instrument, showing the coefficient and
robust standard error stacked within a single cell using ``\makecell``.  A
short summary block (partial F-statistic, KP rk Wald F and sample size) is
appended below the coefficient block.
"""

from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# 1)  Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "firm_scaling"
RAW_DIR = PROJECT_ROOT / "results" / "raw" / SPEC
INPUT_CSV = RAW_DIR / "first_stage.csv"

OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_first_stage.tex"


# ---------------------------------------------------------------------------
# 2)  Formatting helpers
# ---------------------------------------------------------------------------

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    """Return a centred ``\makecell`` with coefficient and (se)."""
    return rf"\makecell[c]{{{coef:.3f}{stars(p)}\\({se:.3f})}}"


# ---------------------------------------------------------------------------
# 3)  Load data and pivot
# ---------------------------------------------------------------------------

if not INPUT_CSV.exists():
    raise FileNotFoundError(INPUT_CSV)

df = pd.read_csv(INPUT_CSV)

# Lists preserve the desired row/column order
ENDOVARS = ["var3", "var5"]          # dependent vars (columns)
# Human-readable labels -------------------------------------------------------

COL_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

PARAM_LABEL = {
    "var6": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) $",
    "var7": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Preserve the CSV row ordering for the instruments so the table lines up with
# the first-stage regression output.
PARAMS   = list(df["param"].unique())  # instrument list (rows)


# ---------------------------------------------------------------------------
# 4)  Build LaTeX table line-by-line
# ---------------------------------------------------------------------------

lines: list[str] = []

lines.append(r"% Auto-generated first-stage estimates – Firm Scaling")
lines.append(r"\begin{table}[H]")
lines.append(r"\centering")
lines.append(r"\caption{First-Stage Estimates – Firm Scaling}")
lines.append(r"\label{tab:firm_scaling_first_stage}")

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
nc = 1 + len(ENDOVARS)                      # stub + 2 endovars
col_spec = "l" + "c" * len(ENDOVARS)
lines.append(rf"\begin{{tabular}}{{{col_spec}}}")
lines.append(r"\toprule")

# Title row spanning the two dependent-variable columns
lines.append(r" & \multicolumn{2}{c}{Dependent variable}\\")
lines.append(r"\cmidrule(lr){2-3}")

# Stub plus pretty-printed column names
header_cells = ["Instrument"] + [COL_LABEL.get(c, c) for c in ENDOVARS]
lines.append(" & ".join(header_cells) + r"\\")
lines.append(r"\midrule")

# ------------------------------------------------------------------
# Coefficient rows
# ------------------------------------------------------------------
for param in PARAMS:
    # Human-readable stub (default to raw name if no mapping found)
    cells = [PARAM_LABEL.get(param, param)]
    for endo in ENDOVARS:
        sub = df.query("param == @param and endovar == @endo")
        if not sub.empty:
            c = cell(*sub.iloc[0][["coef", "se", "pval"]])
        else:
            c = ""
        cells.append(c)
    # End each table row with "\\" but *without* a trailing space – trailing
    # whitespace after the row separator confuses TeX's look-ahead and, in our
    # case, caused a mysterious "Misplaced \noalign" error at the subsequent
    # \cmidrule.  See https://tex.stackexchange.com/q/371728 for background.
    lines.append(" & ".join(cells) + r"\\")

# ------------------------------------------------------------------
# FE indicator rows -------------------------------------------------
# ------------------------------------------------------------------
lines.append(r"\midrule")

# Use a single backslash so LaTeX sees the actual `\checkmark` command.  A raw
# string would keep the double backslash sequence verbatim, which then renders
# as a line-break command (``\\``) followed by the literal text *checkmark*,
# consequently breaking the table during compilation.
for label, include in [("Time FE", True), ("Firm FE", True)]:
    marks = ["$\\checkmark$" if include else "" for _ in ENDOVARS]
    lines.append(" & ".join([label] + marks) + r"\\")

# ------------------------------------------------------------------
# Summary statistics ------------------------------------------------
# ------------------------------------------------------------------
lines.append(r"\midrule")

def first_value(col: str, endo: str):
    sub = df.query("endovar == @endo").head(1)
    return sub.iloc[0][col] if not sub.empty else float("nan")


# Build the summary rows – we drop the KP rk Wald F statistic per newer spec.
summary_rows = {
    "Partial F": [first_value("partialF", e) for e in ENDOVARS],
    "N":         [int(first_value("nobs", e)) for e in ENDOVARS],
}

for label, vals in summary_rows.items():
    val_str = [f"{v:.2f}" if isinstance(v, float) else f"{v:,}" for v in vals]
    lines.append(" & ".join([label] + val_str) + r"\\")

lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
lines.append(r"\end{table}")

# ---------------------------------------------------------------------------
# 5)  Write file
# ---------------------------------------------------------------------------
OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")
