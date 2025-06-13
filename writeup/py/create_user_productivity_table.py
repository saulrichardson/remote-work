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

# ---------------------------------------------------------------------------
# Panel‐sample variant handling
# ---------------------------------------------------------------------------
#  • "unbalanced" (default) — original filenames are kept to avoid breaking
#    existing paths in the LaTeX source and elsewhere.
#  • "balanced" / "precovid" / "balanced_pre" — variant suffix appended to every
#    directory name to prevent clobbering the default outputs.
# ---------------------------------------------------------------------------

DEFAULT_VARIANT = "unbalanced"

# The variant identifier is injected further below once CLI arguments have
# been parsed.  We build the path *templates* here so that the rest of the
# script can stay untouched.

SPEC_BASE = "user_productivity"
RAW_DIR = PROJECT_ROOT / "results" / "raw"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# ---------------------------------------------------------------------------
# Outcome labels – clarify that variables are *percentile ranks* of
# contributions.  Abbreviate where space is tight.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Outcome labels
#  • q100 variables are percentile‐ranked contributions
#  • _we variables are winsorised at 1/99 levels (raw contribution counts)
# ---------------------------------------------------------------------------

OUTCOME_LABEL = {
    "total_contributions_q100":      "Total Contrib. (pct. rk)",
    "restricted_contributions_q100": "Restricted (pct. rk)",
    "total_contributions_we":        "Total (wins.)",
    "restricted_contributions_we":   "Restr. (wins.)",
}

# Panel B should omit the “Total” column because Total Contributions are
# already displayed in Panel A.
OUTCOME_LABEL_B = {k: v for k, v in OUTCOME_LABEL.items() if k != "total_contributions_q100"}

# ---------------------------------------------------------------------------
# Fixed-effect variants to display
# ---------------------------------------------------------------------------
# The alternative‐FE Stata script now exports the following additional tags
# that were not previously shown: useryh, industrytime, msatime,
# msaindustrytime.  We extend ``TAG_ORDER`` accordingly, keeping the original
# six columns first so that previously generated PDFs do not reorder results.

# ---------------------------------------------------------------------------
# Only display variants that include *at least* Firm + User + Time fixed
# effects.  These are the specifications of substantive interest once all
# baseline FEs are on.
#  → keep: fyhu, firmbyuseryh, industrytime, msatime, msaindustrytime
#  → drop: none, firm, time, fyh, useryh (not shown earlier)
# ---------------------------------------------------------------------------

TAG_ORDER = [
    "init",            # 0) Baseline spec (no startup interaction), Firm+User+Time FE
    "fyhu",            # 1) Firm + User + Time FE with interaction
    "firmbyuseryh",    # 2) Firm×User pair + Time FE
    "industrytime",    # 3) + Industry × Time FE
    "msatime",         # 4) + MSA × Time FE
    "msaindustrytime", # 5) + Industry × Time + MSA × Time FE
]

# Generate column labels dynamically.
COL_LABELS = [f"({i})" for i in range(1, len(TAG_ORDER) + 1)]

# ------------------------------
# Indicator-row mappings
# ------------------------------
# Keys omitted from the mapping default to ``False`` when accessed via
# ``dict.get`` in ``indicator_row``.

FIRM_FE_INCLUDED = {
    # pure firm FE appears as `firm_id` (not interacted)
    "init": True,
    "fyhu": True,
    "industrytime": True,
    "msatime": True,
    "msaindustrytime": True,
}

USER_FE_INCLUDED = {
    # pure user FE appears as `user_id`
    "init": True,
    "fyhu": True,
    "industrytime": True,
    "msatime": True,
    "msaindustrytime": True,
}

# Generic Time FE (yh) – appears only when `yh` is in the absorb list by itself.
TIME_FE_INCLUDED = {
    "init": True,
    "fyhu": True,
    "firmbyuseryh": True,
}

# Additional interacted FE dimensions ---------------------------------------
# Industry × Year FE
IND_FE_INCLUDED = {
    "init": False,
    "industrytime": True,
    "msaindustrytime": True,
}

# MSA × Year FE
MSA_FE_INCLUDED = {
    "init": False,
    "msatime": True,
    "msaindustrytime": True,
}

# Firm × User FE
FIRMUSER_FE_INCLUDED = {
    "init": False,
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
    ncols = 1 + len(OUTCOME_LABEL_B)
    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: Additional Outcomes}}}}}}\\"
    panel_row += "\n\\addlinespace"

    dep_hdr = rf" & \multicolumn{{{len(OUTCOME_LABEL_B)}}}{{c}}{{Outcome}} \\"  # merge hdr
    cmid = rf"\cmidrule(lr){{2-{ncols}}}"
    sub_hdr = " & ".join(["", *OUTCOME_LABEL_B.values()]) + r" \\"  # subheader

    rows = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for out in OUTCOME_LABEL_B:
            sub = df.query("model_type==@model and outcome==@out and param==@param")
            cells.append(cell(*sub.iloc[0][["coef", "se", "pval"]]) if not sub.empty else "")
        rows.append(" & ".join(cells) + r" \\")
    coef_block = "\n".join(rows)

    pre_mean_row = build_pre_mean_row(
        df,
        list(OUTCOME_LABEL_B),
        filter_expr=f"model_type=='{model}' and outcome=='{{k}}'",
    )

    obs_row = build_obs_row(
        df,
        list(OUTCOME_LABEL_B),
        filter_expr=f"model_type=='{model}' and outcome=='{{k}}'",
    )

    kp_row = build_kp_row(
        df,
        list(OUTCOME_LABEL_B),
        filter_expr=f"model_type=='{model}' and outcome=='{{k}}'",
    ) if include_kp else ""

    # One column for the parameter label plus a column per *additional* outcome
    # (Total Contributions is already covered in Panel A).
    col_fmt = column_format(len(OUTCOME_LABEL_B))
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
    panel_row = rf"\multicolumn{{{ncols}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: Total Contrib. (pct. rk)}}}}}}\\"
    panel_row += "\n\\addlinespace"

    dep_hdr = ""
    cmid = ""
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
        indicator_row("Industry $\\times$ Time FE", IND_FE_INCLUDED),
        indicator_row("MSA $\\times$ Time FE", MSA_FE_INCLUDED),
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
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default=DEFAULT_VARIANT,
        help="Which user_panel sample variant to load (default: %(default)s)",
    )
    args = parser.parse_args()

    model = "IV" if args.model_type.lower() == "iv" else "OLS"
    include_kp = model == "IV"

    # ------------------------------------------------------------------
    # Construct variant-aware input/output paths
    # ------------------------------------------------------------------

    dir_base = f"{SPEC_BASE}_{args.variant}"
    dir_alt = f"{SPEC_BASE}_alternative_fe_{args.variant}"
    dir_init = f"{SPEC_BASE}_initial_{args.variant}"

    input_base = RAW_DIR / dir_base / "consolidated_results.csv"
    input_alt = RAW_DIR / dir_alt / "consolidated_results.csv"
    input_init = RAW_DIR / dir_init / "consolidated_results.csv"

    tex_stub = f"{SPEC_BASE}_{args.variant}_{args.model_type}"
    tex_label_stub = f"user_productivity_{args.variant}_{args.model_type}"

    output_tex = PROJECT_ROOT / "results" / "cleaned" / f"{tex_stub}.tex"
    variant_tex = args.variant.replace("_", r"\_")
    caption = f"User Productivity ({variant_tex}) -- {model}"
    label = f"tab:{tex_label_stub}"

    # ------------------------------------------------------------------
    # Robustness: some panel variants (e.g. balanced_pre) were generated
    # only for the baseline specification.  If the alternative‐FE or
    # initial‐spec folders are absent we still want to build Panel A so the
    # overall report compiles.  We therefore *require* the baseline CSV but
    # silently skip the others when missing.
    # ------------------------------------------------------------------

    if not input_base.exists():
        raise FileNotFoundError(input_base)

    df_base = pd.read_csv(input_base)

    if input_alt.exists():
        df_alt = pd.read_csv(input_alt)
    else:
        df_alt = pd.DataFrame()

    if input_init.exists():
        df_init = pd.read_csv(input_init).copy()
        df_init["fe_tag"] = "init"
    else:
        df_init = pd.DataFrame()
    df_init["fe_tag"] = "init"

    df_fe = pd.concat([df_init, df_alt], ignore_index=True, sort=False)
    if df_fe.empty:
        print("Warning: no alternative-FE results found; Panel B will be omitted.")

    tex_lines = [
        "% Auto-generated user productivity table",
        "",
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\centering",
    ]

    if not df_fe.empty:
        tex_lines.append(build_panel_fe(df_fe, model, include_kp).rstrip())
    tex_lines.append(build_panel_base(df_base, model, include_kp).rstrip())
    tex_lines.append(r"\end{table}")

    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {output_tex.resolve()}")


if __name__ == "__main__":
    main()
