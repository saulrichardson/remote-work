#!/usr/bin/env python3
"""Generate a regression table for the Firm-Scaling specification.

Consolidates OLS and IV estimates across two FE variants.
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



SPEC_BASE = "firm_scaling"
RAW_DIR = PROJECT_ROOT / "results" / "raw"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}


OUTCOME_SHORT = {
    "growth_rate_we": r"\makecell[c]{Growth\\(wins.)}",
    "join_rate_we":   r"\makecell[c]{Join\\(wins.)}",
    "leave_rate_we":  r"\makecell[c]{Leave\\(wins.)}",
}





COL_CONFIG = [
    ("growth_rate_we", "init"),  # (1)
    ("growth_rate_we", "fyh"),   # (2)
    ("join_rate_we",   "fyh"),   # (3)
    ("leave_rate_we",  "fyh"),   # (4)
]





FIRM_FE_INCLUDED = {"init": True, "fyh": True}

# Generic year FE (yh) only appears in `fyh` among the displayed tags.
TIME_FE_INCLUDED = {
    "init": True,
    "fyh": True,
}




STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
TABLE_WIDTH = r"\linewidth"
TABLE_ENV = "tabularx"




# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""






def column_format(n_numeric: int) -> str:
    # one label column, then each X gets 4pt of padding on left & right
    pad = r"@{\hspace{4pt}}"
    body = (pad + r">{\centering\arraybackslash}X" + pad) * n_numeric
    return "l" + body




PREAMBLE_FLEX = r"""{\scriptsize%
\setlength{\tabcolsep}{3pt}%
\renewcommand{\arraystretch}{0.95}%
\begin{adjustbox}{max width=\linewidth, max height=0.9\textheight, center}%
"""
POSTAMBLE_FLEX = r"""\end{adjustbox}}"""

def build_panel_single(df: pd.DataFrame, model: str, include_kp: bool) -> str:
    """Return LaTeX code for a single‐panel table with six columns defined in
    COL_CONFIG.  Each tuple in COL_CONFIG is (outcome, fe_tag)."""

    column_tags = [tag for _, tag in COL_CONFIG]
    col_nums = [f"({i})" for i in range(1, len(COL_CONFIG) + 1)]
    header_nums = " & ".join(["", *col_nums]) + r" \\"
    sub_hdr = " & ".join(["", *[OUTCOME_SHORT[o] for o, _ in COL_CONFIG]]) + r" \\"

    # build rows of coefficients + standard errors
    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for outcome, tag in COL_CONFIG:
            sub = df.query(
                "model_type==@model and outcome==@outcome and fe_tag==@tag and param==@param"
            )
            if not sub.empty:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                cells.append(f"\\makecell[c]{{{coef:.2f}{stars(pval)}\\\\({se:.2f})}}")
            else:
                cells.append("")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    # build indicator rows
    def ind_row(label, mapping):
        marks = [r"$\checkmark$" if mapping.get(t, False) else "" for t in column_tags]
        return " & ".join([label] + marks) + r" \\"

    ind_rows = "\n".join([
        ind_row("Time FE", TIME_FE_INCLUDED),
        ind_row("Firm FE", FIRM_FE_INCLUDED),
    ])

    # build summary rows
    def stat_row(label, field, fmt=None):
        vals = []
        for outcome, tag in COL_CONFIG:
            sub = df[
                (df["model_type"] == model) &
                (df["outcome"] == outcome) &
                (df["fe_tag"] == tag)
            ].head(1)
            if sub.empty or pd.isna(sub.iloc[0].get(field, None)):
                vals.append("")
            else:
                v = sub.iloc[0][field]
                vals.append(fmt.format(v) if fmt else str(v))
        return " & ".join([label] + vals) + r" \\"

    pre_mean_row = stat_row("Pre-COVID mean", "pre_mean", "{:.2f}")
    obs_row      = stat_row("N",           "nobs",    "{:,}")
    kp_row       = stat_row("KP rk Wald F", "rkf",    "{:.2f}") if include_kp else ""

    # assemble the tabularx block
    col_fmt = column_format(len(COL_CONFIG))
    tabular = textwrap.dedent(rf"""
    \begin{{{TABLE_ENV}}}{{{TABLE_WIDTH}}}{{{col_fmt}}}
    {TOP}
    {header_nums}
    {MID}
    {sub_hdr}
    {MID}
    {coef_block}
    {MID}
    {ind_rows}
    {MID}
    {pre_mean_row}
    {obs_row}
    {kp_row}
    {BOTTOM}
    \end{{{TABLE_ENV}}}""")

    # wrap in adjustbox + spacing tweaks + small font
    return PREAMBLE_FLEX + tabular + POSTAMBLE_FLEX



# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Create user productivity regression table")
    parser.add_argument("--model-type", choices=["ols", "iv"], default="ols")
    args = parser.parse_args()

    model = "IV" if args.model_type.lower() == "iv" else "OLS"
    include_kp = model == "IV"

    # ------------------------------------------------------------------
    # Construct variant-aware input/output paths
    # ------------------------------------------------------------------

    dir_alt = f"{SPEC_BASE}"
    dir_init = f"{SPEC_BASE}_initial"

    input_alt = RAW_DIR / dir_alt / "consolidated_results.csv"
    input_init = RAW_DIR / dir_init / "consolidated_results.csv"

    tex_stub = f"{SPEC_BASE}_{args.model_type}"

    output_tex = PROJECT_ROOT / "results" / "cleaned" / f"{tex_stub}.tex"
    caption = f"Firm Scaling — {model}"
    label   = f"tab:firm_scaling_{model.lower()}"

    # ------------------------------------------------------------------
    # Load regression outputs
    #   • input_base  – baseline specification (includes extra outcomes)
    #   • input_init  – baseline FE variant (Total contrib. only)
    #   • input_alt   – alternative FE variants (Total contrib. only)
    # ------------------------------------------------------------------




    df_init = pd.read_csv(input_init).copy()
    df_init["fe_tag"] = "init"

    df_alt = pd.read_csv(input_alt)
    df_alt["fe_tag"] = "fyh"

    # Combine FE variants (Panel A) ------------------------------------
    df_fe = pd.concat([df_init, df_alt], ignore_index=True, sort=False)

    # ------------------------------------------------------------------
    # Build single‐panel table (custom column configuration)
    # ------------------------------------------------------------------

    panel_single = build_panel_single(df_fe, model, include_kp).rstrip()

    tex_body = [panel_single]

    tex_lines = [
        r"\begin{table}[H]",
        r"\centering",
        r"{\scriptsize\centering",          # ← add \centering here
        rf"  \caption{{{caption}}}",
        rf"  \label{{{label}}}",
        r"}",
        r"\centering",
        *tex_body,
        r"\end{table}",
    ]

    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {output_tex.resolve()}")


if __name__ == "__main__":
    main()
