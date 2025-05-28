#!/usr/bin/env python3
"""Generate a two-panel regression table for the User-Productivity specification.

Use ``--model-type`` to choose between OLS and IV variants. Query filters,
caption text and optional Kleibergen--Paap rows are adjusted accordingly.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import textwrap

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "user_productivity"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
INPUT_BASE = RAW_DIR / SPEC / "consolidated_results.csv"
INPUT_ALT = RAW_DIR / f"{SPEC}_alternative_fe" / "consolidated_results.csv"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOME_LABEL = {
    "total_contributions_q100":     "Total",
    "restricted_contributions_q100": "Restricted",
}

TAG_ORDER   = ["none", "firm", "time", "fyh", "fyhu", "firmbyuseryh"]
COL_LABELS  = [f"({i})" for i in range(1, len(TAG_ORDER)+1)]

FIRM_FE_INCLUDED = {
    "firm": True,
    "fyh":  True,
    "fyhu": True,
    "firmbyuseryh": False,
}
USER_FE_INCLUDED = {
    "fyhu": True,
    "firmbyuseryh": False,
}
TIME_FE_INCLUDED = {
    "time": True,
    "fyh":  True,
    "fyhu": True,
    "firmbyuseryh": True,
}
FIRMUSER_FE_INCLUDED = {
    "firmbyuseryh": True,
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
PANEL_SEP = r"\specialrule{\lightrulewidth}{0pt}{0pt}"
TABLE_WIDTH = r"\dimexpr\textwidth + 2cm\relax"
TABLE_ENV = "tabularx"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def indicator_row(label: str, mapping: dict[str, bool]) -> str:
    checks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in TAG_ORDER]
    return " & ".join([label] + checks) + r" \\"


def build_obs_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    cells = ["N"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        n = int(sub.iloc[0]["nobs"]) if not sub.empty else 0
        cells.append(f"{n:,}")
    return " & ".join(cells) + r" \\"


def build_pre_mean_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    """Return a row of pre-COVID means."""
    import pandas as pd

    cells = ["Pre-COVID mean"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        val = sub.iloc[0]["pre_mean"] if "pre_mean" in sub.columns and not sub.empty else float("nan")
        cells.append(f"{val:.2f}" if pd.notna(val) else "")
    return " & ".join(cells) + r" \\"


def build_kp_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
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

# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------

def build_panel_base(df: pd.DataFrame, model: str, include_kp: bool) -> str:
    ncols = 1 + len(OUTCOME_LABEL)
    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: Base Specification}}}}}}\\"
    panel_row += "\n\\addlinespace"

    dep_hdr = rf" & \multicolumn{{{len(OUTCOME_LABEL)}}}{{c}}{{Outcome}} \\"  # merge hdr
    cmid = rf"\cmidrule(lr){{2-{ncols}}}"
    sub_hdr = " & ".join(["", *OUTCOME_LABEL.values()]) + r" \\"  # subheader

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for out in OUTCOME_LABEL:
            sub = df.query("model_type==@model and outcome==@out and param==@param")
            cells.append(cell(*sub.iloc[0][["coef", "se", "pval"]]) if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    pre_mean_row = build_pre_mean_row(
        df,
        list(OUTCOME_LABEL),
        filter_expr=f"model_type=='{model}' and outcome=='{{k}}'",
    )

    obs_row = build_obs_row(
        df,
        list(OUTCOME_LABEL),
        filter_expr=f"model_type=='{model}' and outcome=='{{k}}'",
    )

    kp_row = build_kp_row(
        df,
        list(OUTCOME_LABEL),
        filter_expr=f"model_type=='{model}' and outcome=='{{k}}'",
    ) if include_kp else ""

    col_fmt = column_format(len(OUTCOME_LABEL))
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
    {pre_mean_row}
    {obs_row}
    {kp_row}
    {bottom}
    \end{{{TABLE_ENV}}}""")


def build_panel_fe(df: pd.DataFrame, model: str, include_kp: bool) -> str:
    ncols = 1 + len(TAG_ORDER)
    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: FE Variants}}}}}}\\"
    panel_row += "\n\\addlinespace"

    dep_hdr = rf" & \multicolumn{{{len(TAG_ORDER)}}}{{c}}{{Total Contributions}} \\"  # one outcome
    cmid = rf"\cmidrule(lr){{2-{ncols}}}"
    header = " & ".join(["", *COL_LABELS]) + r" \\"  # column labels

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for tag in TAG_ORDER:
            sub = df.query(
                "model_type==@model and outcome=='total_contributions_q100' and fe_tag==@tag and param==@param"
            )
            cells.append(cell(*sub.iloc[0][["coef", "se", "pval"]]) if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    # Note: we omit the pre‐COVID mean for the FE‐variant panel to avoid
    # repeating the same statistic that appears in the baseline panel below.
    pre_mean_row = ""  # intentionally left blank

    obs_row = build_obs_row(
        df,
        TAG_ORDER,
        filter_expr=f"model_type=='{model}' and outcome=='total_contributions_q100' and fe_tag=='{{k}}'",
    )

    kp_row = build_kp_row(
        df,
        TAG_ORDER,
        filter_expr=f"model_type=='{model}' and outcome=='total_contributions_q100' and fe_tag=='{{k}}'",
    ) if include_kp else ""

    ind_rows = "\n".join([
        indicator_row("Time FE", TIME_FE_INCLUDED),
        indicator_row("Firm FE", FIRM_FE_INCLUDED),
        indicator_row("User FE", USER_FE_INCLUDED),
        indicator_row("Firm $\\times$ User FE", FIRMUSER_FE_INCLUDED),
    ])

    # Collect optional statistic rows, skipping any that are intentionally
    # blank (e.g., pre_mean_row).
    stats_block = "\n".join(row for row in [pre_mean_row, obs_row, kp_row] if row)

    col_fmt = column_format(len(TAG_ORDER))
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
    {stats_block}
    {bottom}
    \end{{{TABLE_ENV}}}""")
# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Create user productivity regression table")
    parser.add_argument("--model-type", choices=["ols", "iv"], default="ols")
    args = parser.parse_args()

    model = "IV" if args.model_type.lower() == "iv" else "OLS"
    include_kp = model == "IV"

    output_tex = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_{args.model_type}.tex"
    caption = f"User Productivity -- {model}"
    label = f"tab:user_productivity_{args.model_type}"

    if not INPUT_BASE.exists():
        raise FileNotFoundError(INPUT_BASE)
    if not INPUT_ALT.exists():
        raise FileNotFoundError(INPUT_ALT)

    df_base = pd.read_csv(INPUT_BASE)
    df_alt = pd.read_csv(INPUT_ALT)

    tex_lines = [
        "% Auto-generated user productivity table",
        "",
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\centering",
    ]

    tex_lines.append(build_panel_fe(df_alt, model, include_kp).rstrip())
    tex_lines.append(build_panel_base(df_base, model, include_kp).rstrip())
    tex_lines.append(r"\end{table}")

    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {output_tex.resolve()}")


if __name__ == "__main__":
    main()
