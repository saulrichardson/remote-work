#!/usr/bin/env python3
"""
Build a **two‑panel** LaTeX table of OLS results for the Firm‑Scaling project.

* **Panel A** – Base specification: Growth, Join, Leave (OLS).
* **Panel B** – Growth only, four FE specifications.

Formatting tweaks (May 18 2025):
* Drop `var4` rows.
* Custom math labels for `var3` and `var5`.
* Use `\makecell{}` (requires the *makecell* package) so each coefficient and
  its standard error render in the **same cell** (no line‑breaking issues).
"""
from pathlib import Path
import pandas as pd
import textwrap         


# -----------------------------------------------------------------------------
# 1) Paths & constants
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "firm_scaling"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
INPUT_BASE = RAW_DIR / SPEC / "consolidated_results.csv"
INPUT_ALT = RAW_DIR / f"{SPEC}_alternative_fe" / "consolidated_results.csv"
OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_ols.tex"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOME_LABEL = {
    "growth_rate_we": "Growth",
    "join_rate_we": "Join",
    "leave_rate_we": "Leave",
}

TAG_ORDER = ["none", "firm", "time", "fyh"] 
COL_LABELS = ["(1)", "(2)", "(3)", "(4)"]

FIRM_FE_INCLUDED = {"fyh": True, "time": False, "firm": True, "none": False}
TIME_FE_INCLUDED = {"fyh": True, "time": True, "firm": False, "none": False}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

# -----------------------------------------------------------------------------
# 2) Helper functions
# -----------------------------------------------------------------------------

def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    """Return LaTeX makecell with coef and SE."""
    return rf"\makecell[c]{{{coef:.3f}{stars(p)}\\({se:.3f})}}"




def indicator_row(label: str,
                  mapping: dict[str, bool],
                  tag_order: list[str] = TAG_ORDER) -> str:
    """
    Build one LaTeX row that shows ✓ under the columns whose tag
    is True in *mapping*.

    Parameters
    ----------
    label : str
        Left-hand text that describes the row (e.g. "Time FE").
    mapping : dict[str, bool]
        Keys are tag names, values are booleans (True → put a ✓).
    tag_order : list[str], optional
        The column order.  Defaults to the global TAG_ORDER.

    Returns
    -------
    str
        A LaTeX string like
        "Time FE &   & \\checkmark &   & \\checkmark \\\\"
    """
    checks = [r"$\checkmark$" if mapping.get(tag, False) else ""
              for tag in tag_order]
    return " & ".join([label] + checks) + r" \\"


TOP    = r"\toprule"
MID    = r"\midrule"
BOTTOM = r"\bottomrule"

PANEL_SEP = r"\specialrule{\lightrulewidth}{0pt}{0pt}" 

# -------------------------------------------------------------------------
#  Panel builders – cleaner booktabs look
# -------------------------------------------------------------------------
TABLE_WIDTH = r"\textwidth"                       # unchanged

# -----------------------------------------------------------------
# Shared helper
# -----------------------------------------------------------------
def build_obs_row(df: pd.DataFrame, keys: list[str], *,
                  filter_expr: str) -> str:
    """
    """
    cells = ["Observations"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k))
        n    = int(sub.iloc[0]["nobs"]) if not sub.empty else 0
        cells.append(f"{n:,}")
    return " & ".join(cells) + r" \\"

# ------------------------------------------------------------------
# 1)  Panel A  – all scaling outcomes (OLS)
# ------------------------------------------------------------------
def build_panel_a(df: pd.DataFrame) -> str:
    ncIV = 1 + len(OUTCOME_LABEL)

    panel_row = rf"\multicolumn{{{ncIV}}}{{@{{}}l}}{{" \
                rf"\textbf{{\uline{{Panel A: All Outcomes}}}}}}\\"
    panel_row += "\n\\addlinespace"

    # header: three outcomes grouped under one centred “Outcome” title
    dep_hdr = r" & \multicolumn{3}{c}{Outcome} \\"
    cmid    = r"\cmidrule(lr){2-4}"                            # thin rule
    #cmid = r"\cmidrule(lr){2-4}\addlinespace[-\belowrulesep]" 
    sub_hdr = " & ".join([""] + [OUTCOME_LABEL[o]
                                   for o in OUTCOME_LABEL]) + r" \\"

    # coefficient rows
    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for out in OUTCOME_LABEL:
            sub = df.query("model_type=='OLS' and outcome==@out and param==@param")
            cells.append(cell(*sub.iloc[0][['coef', 'se', 'pval']])
                         if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    obs_row = build_obs_row(
        df,
        list(OUTCOME_LABEL),
        filter_expr="model_type=='OLS' and outcome=='{k}'"
    )

    col_fmt = r"@{}lccc"   
    return textwrap.dedent(rf"""
    \begin{{tabular*}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
    {TOP}
    {panel_row}
    {dep_hdr}
    {cmid}
    {sub_hdr}
    {MID}
    {coef_block}
    {MID}
    {obs_row}
    {PANEL_SEP}   
    \end{{tabular*}}""")

# ------------------------------------------------------------------
#  Panel B  – Growth, FE variants
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# 2)  Panel B  – growth, FE variants
# ------------------------------------------------------------------
def build_panel_b(df: pd.DataFrame) -> str:
    ncIV = 1 + len(TAG_ORDER)           # 1 stub + 4 spec columns

    # bold-underline caption
    panel_row = rf"\multicolumn{{{ncIV}}}{{@{{}}l}}{{" \
                rf"\textbf{{\uline{{Panel B: FE Variants}}}}}}\\"
    panel_row += "\n\\addlinespace"
            

    # --- NEW lines ----------------------------------------------------
    dep_hdr = rf" & \multicolumn{{{len(TAG_ORDER)}}}{{c}}{{Growth}} \\"
    cmid    = rf"\cmidrule(lr){{2-{len(TAG_ORDER)+1}}}"      # thin rule under "Growth"
    # -----------------------------------------------------------------

    header  = " & ".join([""] + COL_LABELS) + r" \\"

    # coefficient rows -------------------------------------------------
    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for tag in TAG_ORDER:
            sub = df.query(
                "model_type=='OLS' and outcome=='growth_rate_we' "
                "and fe_tag==@tag and param==@param"
            )
            cells.append(
                cell(*sub.iloc[0][['coef', 'se', 'pval']]) if not sub.empty else ""
            )
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    obs_row = build_obs_row(
        df, TAG_ORDER,
        filter_expr=("model_type=='OLS' and outcome=='growth_rate_we' "
                     "and fe_tag=='{k}'")
    )
    
    # ✓ indicator block (no trailing \\)
    ind_rows = "\n".join([
        indicator_row("Time FE",  TIME_FE_INCLUDED),
        indicator_row("Firm FE",  FIRM_FE_INCLUDED)
    ])

    col_fmt = r"@{}l" + "c"*len(TAG_ORDER)         
    return textwrap.dedent(rf"""
    \begin{{tabular*}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
    {panel_row}
    {dep_hdr}
    {cmid}
    {header}
    {MID}
    {coef_block}
    {MID}
    {obs_row}
    {MID}
    {ind_rows}
    {BOTTOM}
    \end{{tabular*}}""")

# -----------------------------------------------------------------------------
# 3) Main driver
# -----------------------------------------------------------------------------

def main() -> None:
    if not INPUT_BASE.exists():
        raise FileNotFoundError(f"Missing base CSV: {INPUT_BASE}")
    if not INPUT_ALT.exists():
        raise FileNotFoundError(f"Missing alternative FE CSV: {INPUT_ALT}")

    df_base = pd.read_csv(INPUT_BASE)
    df_alt = pd.read_csv(INPUT_ALT)

    # ------------------------------------------------------------------
    # Build the output LaTeX string – **real** new-line characters only.      
    # Using "\n" previously wrote the *literal* back-slash–n sequence to disk
    # which causes a LaTeX compilation error. We now construct the document
    # line-by-line and join with "\n" so that the written file contains
    # proper line breaks.
    # ------------------------------------------------------------------

    tex_lines: list[str] = []

    tex_lines.append("% ------------------------------------------------------------------")
    tex_lines.append("%  Firm-Scaling: Two-panel OLS results")
    tex_lines.append("% ------------------------------------------------------------------")
    tex_lines.append("")

    tex_lines.append(r"\begin{table}[H]")
    tex_lines.append(r"\centering")
    
    # ----------------- NEW LINES -----------------
    tex_lines.append(r"\caption{Firm Scaling OLS}")
    tex_lines.append(r"\label{tab:firm_scaling_ols}")   # optional for \ref{}
    tex_lines.append(r"\centering")

    # Panel A and Panel B (helpers already return strings with trailing \n)
    # The helper builders still embed *escaped* new-line sequences ("\\n").
    # Convert those to real new-lines so LaTeX does not see the two-character
    # token "\\n" (which triggers an \undefined control sequence error).
    panel_a = build_panel_a(df_base).rstrip()
    panel_b = build_panel_b(df_alt).rstrip()

    tex_lines.append(panel_a)
    tex_lines.append(r"\vspace{0.1\baselineskip}")    # <<< extra gap
    tex_lines.append(panel_b)

    #tex_lines.append(r"\vspace{0.5em}")
    #tex_lines.append(r"\footnotesize Notes: Coefficients shown with robust standard errors in parentheses. "
    #                 r"Significance: *** $p<0.01$, ** $p<0.05$, * $p<0.10$.")
    tex_lines.append(r"\end{table}")

    tex_output = "\n".join(tex_lines) + "\n"  # final newline for POSIX friendliness

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text(tex_output)
    print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")


if __name__ == "__main__":
    main()

