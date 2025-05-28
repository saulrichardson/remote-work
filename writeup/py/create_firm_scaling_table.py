#!/usr/bin/env python3
"""Generate a two-panel regression table for the Firm-Scaling specification.

This consolidates the OLS and IV variants. Use ``--model-type`` to select the
underlying model (``ols`` or ``iv``). The script adjusts query filters,
output paths and caption text accordingly. Kleibergen--Paap rows are included
only for the IV specification.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import textwrap
import re

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

SPEC = "firm_scaling"
RAW_DIR = PROJECT_ROOT / "results" / "raw"
INPUT_BASE = RAW_DIR / SPEC / "consolidated_results.csv"
INPUT_ALT = RAW_DIR / f"{SPEC}_alternative_fe" / "consolidated_results.csv"

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

TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
PANEL_SEP = r"\specialrule{\lightrulewidth}{0pt}{0pt}"
PANEL_GAP = r"\addlinespace[0.75em]"

TABLE_WIDTH = r"\textwidth"

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


def indicator_row(label: str, mapping: dict[str, bool], tag_order: list[str] = TAG_ORDER) -> str:
    checks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in tag_order]
    return " & ".join([label] + checks) + r" \\"


def build_obs_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    cells = ["N"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k))
        n = int(sub.iloc[0]["nobs"]) if not sub.empty else 0
        cells.append(f"{n:,}")
    return " & ".join(cells) + r" \\""


def build_pre_mean_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    """Return a row showing pre-COVID means for each column."""
    import pandas as pd

    cells = ["Pre-COVID mean"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        val = sub.iloc[0]["pre_mean"] if "pre_mean" in sub.columns and not sub.empty else float("nan")
        cells.append(f"{val:.2f}" if pd.notna(val) else "")
    return " & ".join(cells) + r" \\""


def build_kp_row(df: pd.DataFrame, keys: list[str], *, filter_expr: str) -> str:
    import pandas as pd
    cells = ["KP rk Wald F"]
    for k in keys:
        sub = df.query(filter_expr.format(k=k)).head(1)
        val = sub.iloc[0]["rkf"] if not sub.empty else float("nan")
        cells.append(f"{val:.2f}" if pd.notna(val) else "")
    return " & ".join(cells) + r" \\"

# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------

def build_panel_base(df: pd.DataFrame, model: str, include_kp: bool) -> str:
    ncols = 1 + len(OUTCOME_LABEL)
    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: Base Specification}}}}}}\\[0.3em]"
    panel_row += "\n\\addlinespace"

    dep_hdr = r" & \multicolumn{3}{c}{Outcome} \\"  # header
    cmid = r"\cmidrule(lr){2-4}"
    sub_hdr = " & ".join(["", *[OUTCOME_LABEL[o] for o in OUTCOME_LABEL]]) + r" \\"  # outcomes

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for out in OUTCOME_LABEL:
            sub = df.query("model_type==@model and outcome==@out and param==@param")
            cells.append(cell(*sub.iloc[0][['coef', 'se', 'pval']]) if not sub.empty else "")
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

    col_fmt = r"@{}l@{\extracolsep{\fill}}ccc@{}"
    top = ""
    bottom = BOTTOM
    return textwrap.dedent(rf"""
    \begin{{tabular*}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
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
    \end{{tabular*}}""")


def build_panel_fe(df: pd.DataFrame, model: str, include_kp: bool) -> str:
    ncols = 1 + len(TAG_ORDER)
    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: FE Variants}}}}}}\\[0.3em]"
    panel_row += "\n\\addlinespace"

    dep_hdr = rf" & \multicolumn{{{len(TAG_ORDER)}}}{{c}}{{Growth}} \\"  # one outcome
    cmid = rf"\cmidrule(lr){{2-{ncols}}}"
    header = " & ".join(["", *COL_LABELS]) + r" \\"  # column labels

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for tag in TAG_ORDER:
            sub = df.query(
                "model_type==@model and outcome=='growth_rate_we' and fe_tag==@tag and param==@param"
            )
            cells.append(cell(*sub.iloc[0][['coef', 'se', 'pval']]) if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    pre_mean_row = build_pre_mean_row(
        df,
        TAG_ORDER,
        filter_expr=f"model_type=='{model}' and outcome=='growth_rate_we'",
    )

    obs_row = build_obs_row(
        df,
        TAG_ORDER,
        filter_expr=f"model_type=='{model}' and outcome=='growth_rate_we' and fe_tag=='{{k}}'",
    )

    kp_row = build_kp_row(
        df,
        TAG_ORDER,
        filter_expr=f"model_type=='{model}' and outcome=='growth_rate_we' and fe_tag=='{{k}}'",
    ) if include_kp else ""

    ind_rows = "\n".join([
        indicator_row("Time FE", TIME_FE_INCLUDED),
        indicator_row("Firm FE", FIRM_FE_INCLUDED),
    ])

    col_fmt = r"@{}l@{\extracolsep{\fill}}" + "c" * len(TAG_ORDER) + r"@{}"
    top = TOP
    bottom = (MID + "\n" + PANEL_GAP) if include_kp else PANEL_SEP
    return textwrap.dedent(rf"""
    \begin{{tabular*}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
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
    {pre_mean_row}
    {obs_row}
    {kp_row}
    {bottom}
    \end{{tabular*}}""")


def strip_tabular_star(tex: str) -> str:
    r"""Remove the \begin{tabular*}…\end{tabular*} wrapper AND its top/bottom rules."""
    # trim whitespace so that anchors in the regex match reliably when
    # tabular blocks are indented. Use MULTILINE mode for substitutions
    # because patterns start or end at line boundaries.
    tex = tex.strip()
    # 1) drop the \begin{tabular*}{…}{…} line
    tex = re.sub(r"^\s*\\begin\{tabular\*\}\{.*?\}.*\n", "", tex, flags=re.MULTILINE)
    # 2) drop the \end{tabular*} line
    tex = re.sub(r"\n\s*\\end\{tabular\*\}$", "", tex, flags=re.MULTILINE)
    # 3) drop a leading \toprule or \addlinespace if present
    tex = re.sub(r"^\s*(?:\\toprule|\\addlinespace).*?\n", "", tex, flags=re.MULTILINE)
    # 4) drop a trailing \specialrule, \midrule, \addlinespace or \bottomrule
    tex = re.sub(r"\n\s*(?:\\specialrule.*|\\midrule|\\addlinespace|\\bottomrule)\s*$", "", tex, flags=re.MULTILINE)
    return tex


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Create firm scaling regression table")
    parser.add_argument("--model-type", choices=["ols", "iv"], default="ols")
    args = parser.parse_args()

    model = "IV" if args.model_type.lower() == "iv" else "OLS"
    include_kp = model == "IV"

    output_tex = PROJECT_ROOT / "results" / "cleaned" / f"{SPEC}_{args.model_type}.tex"
    caption = f"Firm Scaling {model}"
    label = f"tab:firm_scaling_{args.model_type}"

    if not INPUT_BASE.exists():
        raise FileNotFoundError(f"Missing base CSV: {INPUT_BASE}")
    if not INPUT_ALT.exists():
        raise FileNotFoundError(f"Missing alternative FE CSV: {INPUT_ALT}")

    df_base = pd.read_csv(INPUT_BASE)
    df_alt = pd.read_csv(INPUT_ALT)

    raw_fe   = build_panel_fe(df_alt,   model, include_kp)
    raw_base = build_panel_base(df_base, model, include_kp)

    body_fe   = strip_tabular_star(raw_fe)
    body_base = strip_tabular_star(raw_base)

    # Single column‐format that matches Panel A’s width (1 label + len(TAG_ORDER) columns)
    col_fmt = "@{}l@{\\extracolsep{\\fill}}" + "c"*len(TAG_ORDER) + "@{}"

    tex_lines = [
        "% Auto-generated firm scaling table",
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular*}}{{{TABLE_WIDTH}}}{{{col_fmt}}}",
        TOP,
        r"\addlinespace",
        # Panel A header (spans all columns)
        rf"\multicolumn{{{1+len(TAG_ORDER)}}}{{l}}{{\textbf{{\uline{{Panel A: FE Variants}}}}}}\\[0.3em]",
        body_fe,
        r"\addlinespace",
        r"\midrule",
        r"\addlinespace",
        # Panel B header (also spans the same number of cols)
        rf"\multicolumn{{{1+len(TAG_ORDER)}}}{{l}}{{\textbf{{\uline{{Panel B: Base Specification}}}}}}\\[0.3em]",
        body_base,
        BOTTOM,
        r"\end{tabular*}",
        r"\end{table}",
    ]

    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {output_tex.resolve()}")

if __name__ == "__main__":
    main()
