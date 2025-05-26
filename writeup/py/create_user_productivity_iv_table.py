#!/usr/bin/env python3
"""
Generate a two-panel **IV** table for the User-Productivity specification.

The structure mirrors create_user_productivity_ols_table.py; only the
`model_type=='IV'` filter differs.
"""

from pathlib import Path
import pandas as pd
import textwrap

# Project paths --------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "user_productivity"
RAW_DIR = PROJECT_ROOT / "results" / "raw"

INPUT_BASE = RAW_DIR / SPEC / "consolidated_results.csv"
INPUT_ALT  = RAW_DIR / f"{SPEC}_alternative_fe" / "consolidated_results.csv"

OUTPUT_TEX = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_iv.tex"

# Constants ------------------------------------------------------------------
PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOME_LABEL = {
    "total_contributions_q100":     "Total",
    "restricted_contributions_q100": "Restricted",
}

# FE-variant column ordering (Panel A)
TAG_ORDER   = ["none", "firm", "time", "fyh", "fyhu", "firmbyuseryh"]
COL_LABELS  = [f"({i})" for i in range(1, len(TAG_ORDER)+1)] 

FIRM_FE_INCLUDED      = {
    "firm": True,
    "fyh":  True,
    "fyhu": True,
    "firmbyuseryh": False,      # ← no stand-alone firm FE
}

USER_FE_INCLUDED      = {
    "fyhu": True,
    "firmbyuseryh": False,      # ← no stand-alone user FE
}

TIME_FE_INCLUDED      = {
    "time": True,
    "fyh":  True,
    "fyhu": True,
    "firmbyuseryh": True,       # ← *does* have year-half FE
}

FIRMUSER_FE_INCLUDED  = {
    #"fyhu": True,
    "firmbyuseryh": True,       # ← has firm × user FE
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

# Helpers --------------------------------------------------------------------


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def indicator_row(label: str, mapping: dict[str, bool]) -> str:
    checks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in TAG_ORDER]
    return " & ".join([label] + checks) + r" \\"  # trailing \\


TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
PANEL_SEP = r"\specialrule{\lightrulewidth}{0pt}{0pt}"
TABLE_WIDTH = r"\textwidth"
TABLE_WIDTH = r"\dimexpr\textwidth + 2cm\relax"




# -----------------------------------------------------------------
# Shared helper – one row, many uses
# -----------------------------------------------------------------
def build_obs_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    """Return a LaTeX row of observation counts."""
    cells = ["N"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        n   = int(sub.iloc[0]["nobs"]) if not sub.empty else 0
        cells.append(f"{n:,}")
    return " & ".join(cells) + r" \\" 

# -----------------------------------------------------------------
#  Kleibergen–Paap rk Wald F helper
# -----------------------------------------------------------------

def build_kp_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    """Return a LaTeX-formatted row reporting the KP rk Wald F statistic."""

    import pandas as pd

    cells = ["KP rk Wald F"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        val = sub.iloc[0]["rkf"] if not sub.empty else float("nan")
        cells.append(f"{val:.2f}" if pd.notna(val) else "")
    return " & ".join(cells) + r" \\" 


def column_format(n_numeric: int) -> str:
    return (
        r"@{}l" +
        "".join([r"@{\hskip 8pt}>{\centering\arraybackslash}X" for _ in range(n_numeric)]) +
        r"@{}"
    )

# Panel builders -------------------------------------------------------------
TABLE_ENV = "tabularx"


def build_panel_base(df: pd.DataFrame) -> str:

    ncols = 1 + len(OUTCOME_LABEL)

    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: Base Specification}}}}}}\\"
    panel_row += "\n\\addlinespace"

    dep_hdr = rf" & \multicolumn{{{len(OUTCOME_LABEL)}}}{{c}}{{Outcome}} \\"  # merge hdr
    cmid    = rf"\cmidrule(lr){{2-{ncols}}}"
    sub_hdr = " & ".join([""] + list(OUTCOME_LABEL.values())) + r" \\"  # Total & Restricted

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for out in OUTCOME_LABEL:
            sub = df.query("model_type=='IV' and outcome==@out and param==@param")
            cells.append(cell(*sub.iloc[0][["coef", "se", "pval"]]) if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    # Observations – by outcome (Total, Restricted)
    obs_row = build_obs_row(
        df,
        list(OUTCOME_LABEL),
        filter_expr="model_type=='IV' and outcome=='{k}'"
    )

    kp_row = build_kp_row(
        df,
        list(OUTCOME_LABEL),
        filter_expr="model_type=='IV' and outcome=='{k}'"
    )


    col_fmt = column_format(len(OUTCOME_LABEL))  # in build_panel_fease
    top = ""
    bottom = BOTTOM

    return textwrap.dedent(rf"""
    \begin{{{TABLE_ENV}}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
    {top}
    {panel_row}
    {dep_hdr}
    {cmid}
    {sub_hdr}
    {MID}
    {coef_block}
    {MID}
    {obs_row}
    {kp_row}
    {bottom}
    \end{{{TABLE_ENV}}}""")



def build_panel_fe(df: pd.DataFrame) -> str:

    ncols = 1 + len(TAG_ORDER)

    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: FE Variants}}}}}}\\"
    panel_row += "\n\\addlinespace"

    dep_hdr = rf" & \multicolumn{{{len(TAG_ORDER)}}}{{c}}{{Total Contributions}} \\"  # one outcome
    cmid    = rf"\cmidrule(lr){{2-{ncols}}}"
    header  = " & ".join([""] + COL_LABELS) + r" \\"  # (1)…(5)

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for tag in TAG_ORDER:
            sub = df.query(
                "model_type=='IV' and outcome=='total_contributions_q100' and fe_tag==@tag and param==@param"
            )
            cells.append(cell(*sub.iloc[0][["coef", "se", "pval"]]) if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    # Observations – by FE tag (none, firm, …)
    obs_row = build_obs_row(
        df,
        TAG_ORDER,
        filter_expr=("model_type=='IV' and outcome=='total_contributions_q100' "
                     "and fe_tag=='{k}'")
    )

    kp_row = build_kp_row(
        df,
        TAG_ORDER,
        filter_expr=("model_type=='IV' and outcome=='total_contributions_q100' "
                     "and fe_tag=='{k}'")
    )

    ind_rows = "\n".join([
        indicator_row("Time FE", TIME_FE_INCLUDED),
        indicator_row("Firm FE", FIRM_FE_INCLUDED),
        indicator_row("User FE", USER_FE_INCLUDED),
        indicator_row("Firm $\\times$ User FE", FIRMUSER_FE_INCLUDED),
    ])


    col_fmt = column_format(len(TAG_ORDER))      # in build_panel_fe
    top = TOP
    bottom = PANEL_SEP

    return textwrap.dedent(rf"""
    \begin{{{TABLE_ENV}}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
    {top}
    {panel_row}
    {dep_hdr}
    {cmid}
    {header}
    {MID}
    {coef_block}
    {MID}
    {ind_rows}
    {MID}
    {obs_row}
    {kp_row}
    {bottom}
    \end{{{TABLE_ENV}}}""")


# Main -----------------------------------------------------------------------

def main() -> None:
    if not INPUT_BASE.exists():
        raise FileNotFoundError(INPUT_BASE)
    if not INPUT_ALT.exists():
        raise FileNotFoundError(INPUT_ALT)

    df_base = pd.read_csv(INPUT_BASE)
    df_alt = pd.read_csv(INPUT_ALT)

    tex_lines = [
        "% Auto-generated IV table – User Productivity",
        "",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{User Productivity -- IV}",
        r"\label{tab:user_productivity_iv}",
        r"\centering",
    ]


    # Show the Panel A (FE variants) before Panel B (base)
    tex_lines.append(build_panel_fe(df_alt).rstrip())
    tex_lines.append(build_panel_base(df_base).rstrip())


    tex_lines.append(r"\end{table}")

    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {OUTPUT_TEX.resolve()}")


if __name__ == "__main__":
    main()
