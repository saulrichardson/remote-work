#!/usr/bin/env python3
"""Generate the combined OLS + IV regression table for the User-Productivity
specification."""

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



SPEC_BASE = "user_productivity"
RAW_DIR = PROJECT_ROOT / "results" / "raw"

# Default sample variant for the script (pre-covid user panel)
DEFAULT_VARIANT = "precovid"

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}


TAG_ORDER = [
    "init",         # 0) Baseline spec – Firm + User + Time FE
    "fyhu",         # 1) Firm + User + Time FE with interaction
    "firmbyuseryh", # 2) Firm × User pair + Time FE
]



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




# Firm × User FE
FIRMUSER_FE_INCLUDED = {
    "init": False,
    "firmbyuseryh": True,
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
TABLE_WIDTH = r"\linewidth"
TABLE_ENV = "tabular*"




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


def column_format(n_numeric: int) -> str:
    # one label column + evenly spaced numeric columns
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"
# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Column configuration for the desired single‐panel layout
# ---------------------------------------------------------------------------

OUTCOME_SETS: dict[str, dict[str, object]] = {
    "total": {
        "columns": [
            ("total_contributions_q100", "init"),
            ("total_contributions_q100", "fyhu"),
            ("total_contributions_q100", "firmbyuseryh"),
            ("total_contributions_we", "firmbyuseryh"),
        ],
        "headers": {
            "total_contributions_q100": r"Rank",
            "total_contributions_we": r"Total",
        },
        "caption_suffix": "",
        "label_suffix": "",
        "filename_suffix": "",
    },
    "restricted": {
        "columns": [
            ("restricted_contributions_q100", "init"),
            ("restricted_contributions_q100", "fyhu"),
            ("restricted_contributions_q100", "firmbyuseryh"),
            ("restricted_contributions_we", "firmbyuseryh"),
        ],
        "headers": {
            "restricted_contributions_q100": r"Rank",
            "restricted_contributions_we": r"Total",
        },
        "caption_suffix": " (Restricted)",
        "label_suffix": "_restricted",
        "filename_suffix": "_restricted",
    },
}

## ---------------------------------------------------------------------------
## Mini-report table preamble (small font, tight spacing, centering wrapper)
## ---------------------------------------------------------------------------
PREAMBLE_FLEX = "\\centering\n"
POSTAMBLE_FLEX = ""

## ---------------------------------------------------------------------------
## Helper builders for the combined table
## ---------------------------------------------------------------------------


def _build_headers(columns: list[tuple[str, str]], header_map: dict[str, str]) -> tuple[str, str, str]:
    col_nums = [f"({i})" for i in range(1, len(columns) + 1)]
    header_nums = " & " + " & ".join(col_nums) + r" \\"  

    groups: list[tuple[str, int]] = []
    idx = 0
    while idx < len(columns):
        outcome, _ = columns[idx]
        span = 1
        while idx + span < len(columns) and columns[idx + span][0] == outcome:
            span += 1
        groups.append((outcome, span))
        idx += span

    header_groups = " & " + " & ".join(
        rf"\multicolumn{{{span}}}{{c}}{{{header_map[outcome]}}}"
        for outcome, span in groups
    ) + r" \\"  

    cmidrules = []
    col_start = 2
    for _, span in groups:
        col_end = col_start + span - 1
        cmidrules.append(rf"\cmidrule(lr){{{col_start}-{col_end}}}")
        col_start = col_end + 1
    cmidrule_line = "\n".join(cmidrules)
    return header_nums, header_groups, cmidrule_line


def _stat_row(
    df: pd.DataFrame,
    model: str,
    columns: list[tuple[str, str]],
    label: str,
    field: str,
    fmt: str,
) -> str:
    cells: list[str] = []
    for outcome, tag in columns:
        sub = df[
            (df["model_type"] == model)
            & (df["outcome"] == outcome)
            & (df["fe_tag"] == tag)
        ].head(1)
        if sub.empty:
            cells.append("")
            continue
        value = sub.iloc[0].get(field)
        if pd.isna(value):
            cells.append("")
        else:
            cells.append(fmt.format(value))
    return " & ".join([label, *cells]) + r" \\"


def _panel_rows(
    df: pd.DataFrame,
    model: str,
    *,
    columns: list[tuple[str, str]],
    column_tags: list[str],
    panel_label: str | None,
    include_kp: bool,
    trailing_midrule: bool,
    include_pre_mean: bool,
) -> list[str]:
    lines: list[str] = []
    if panel_label is not None:
        lines.append(
            rf"\multicolumn{{{len(column_tags)+1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel {panel_label}: {model}}}}}}} \\"
        )
        lines.append(r"\addlinespace[2pt]")

    INDENT = r"\hspace{1em}"
    for param in PARAM_ORDER:
        row = [INDENT + PARAM_LABEL[param]]
        for outcome, tag in columns:
            sub = df[
                (df["model_type"] == model)
                & (df["outcome"] == outcome)
                & (df["fe_tag"] == tag)
                & (df["param"] == param)
            ].head(1)
            if sub.empty:
                row.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                row.append(cell(coef, se, pval))
        lines.append(" & ".join(row) + r" \\")

    def ind_row(label: str, mapping: dict[str, bool]) -> str:
        marks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in column_tags]
        return " & ".join([label, *marks]) + r" \\"

    lines.append(MID)
    lines.extend(
        [
            ind_row("Time FE", TIME_FE_INCLUDED),
            ind_row("Firm FE", FIRM_FE_INCLUDED),
            ind_row("User FE", USER_FE_INCLUDED),
            ind_row(r"Firm $\times$ User FE", FIRMUSER_FE_INCLUDED),
        ]
    )

    lines.append(MID)
    if include_pre_mean:
        lines.append(_stat_row(df, model, columns, "Pre-Covid Mean", "pre_mean", "{:.2f}"))
    if include_kp:
        lines.append(_stat_row(df, model, columns, "KP rk Wald F", "rkf", "{:.2f}"))
    lines.append(_stat_row(df, model, columns, "N", "nobs", "{:,}"))

    if trailing_midrule:
        lines.append(MID)

    return lines


def build_panel_fe(
    df: pd.DataFrame,
    model: str,
    include_kp: bool,
    *,
    columns: list[tuple[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """Legacy helper that keeps compatibility with csv2panel_user."""

    if columns is None or headers is None:
        columns = OUTCOME_SETS["total"]["columns"]
        headers = OUTCOME_SETS["total"]["headers"]

    column_tags = [tag for _, tag in columns]
    header_nums, header_groups, cmidrule_line = _build_headers(columns, headers)
    col_fmt = column_format(len(columns))

    body_lines = _panel_rows(
        df,
        model,
        columns=columns,
        column_tags=column_tags,
        panel_label=None,
        include_kp=include_kp,
        trailing_midrule=False,
        include_pre_mean=True,
    )

    lines = [
        rf"\begin{{{TABLE_ENV}}}{{{TABLE_WIDTH}}}{{{col_fmt}}}",
        TOP,
        header_groups,
        cmidrule_line,
        header_nums,
        MID,
        *body_lines,
        BOTTOM,
        rf"\end{{{TABLE_ENV}}}",
    ]
    return "\n".join(lines)


def build_combined_table(
    df: pd.DataFrame,
    *,
    columns: list[tuple[str, str]],
    headers: dict[str, str],
) -> str:
    column_tags = [tag for _, tag in columns]
    header_nums, header_groups, cmidrule_line = _build_headers(columns, headers)
    col_fmt = column_format(len(columns))

    def _strip_fe_rows(rows: list[str]) -> list[str]:
        killers = (
            "Time FE ",
            "Firm FE ",
            "User FE ",
            "Firm $\\times$ User FE ",
        )
        out: list[str] = []
        for r in rows:
            if any(r.lstrip().startswith(k) for k in killers):
                continue
            if out and out[-1].strip() == MID and r.strip() == MID:
                # collapse duplicate midrules left after removing FE block
                continue
            out.append(r)
        return out

    panel_ols = _panel_rows(
        df,
        "OLS",
        columns=columns,
        column_tags=column_tags,
        panel_label="A",
        include_kp=False,
        trailing_midrule=True,
        include_pre_mean=True,
    )
    panel_ols = _strip_fe_rows(panel_ols)

    panel_iv = _panel_rows(
        df,
        "IV",
        columns=columns,
        column_tags=column_tags,
        panel_label="B",
        include_kp=True,
        trailing_midrule=False,
        include_pre_mean=False,
    )
    panel_iv = _strip_fe_rows(panel_iv)

    # FE rows at bottom only once
    INDENT = r"\hspace{1em}"
    def ind_row(label: str, mapping: dict[str, bool]) -> str:
        marks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in column_tags]
        return " & ".join([INDENT + label, *marks]) + r" \\" 

    fe_header = r"\textbf{Fixed Effects} & " + " & ".join([""] * len(column_tags)) + r" \\" 
    fe_block = [
        fe_header,
        ind_row("Time FE", TIME_FE_INCLUDED),
        ind_row("Firm FE", FIRM_FE_INCLUDED),
        ind_row("User FE", USER_FE_INCLUDED),
        ind_row(r"Firm $\times$ User FE", FIRMUSER_FE_INCLUDED),
    ]

    lines = [
        rf"\begin{{{TABLE_ENV}}}{{{TABLE_WIDTH}}}{{{col_fmt}}}",
        TOP,
        header_groups,
        cmidrule_line,
        header_nums,
        MID,
        *panel_ols,
        *panel_iv,
        MID,
        *fe_block,
        BOTTOM,
        rf"\end{{{TABLE_ENV}}}",
    ]
    return PREAMBLE_FLEX + "\n".join(lines) + POSTAMBLE_FLEX



# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Create user productivity regression table")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default=DEFAULT_VARIANT,
        help="Which user_panel sample variant to load (default: %(default)s)",
    )
    parser.add_argument(
        "--outcome-set",
        choices=list(OUTCOME_SETS.keys()),
        default="total",
        help="Which outcome set to display (default: %(default)s)",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Construct variant-aware input/output paths
    # ------------------------------------------------------------------

    dir_alt = f"{SPEC_BASE}_alternative_fe_{args.variant}"
    dir_init = f"{SPEC_BASE}_initial_{args.variant}"

    input_alt = RAW_DIR / dir_alt / "consolidated_results.csv"
    input_init = RAW_DIR / dir_init / "consolidated_results.csv"

    config = OUTCOME_SETS[args.outcome_set]
    if args.variant == "precovid" and not config["filename_suffix"]:
        filename = "user_productivity_precovid_total.tex"
    else:
        filename = f"{SPEC_BASE}_{args.variant}{config['filename_suffix']}.tex"
    output_tex = PROJECT_ROOT / "results" / "cleaned" / filename

    # ------------------------------------------------------------------
    # Load regression outputs
    #   • input_init  – baseline FE variant (Total contrib. only)
    #   • input_alt   – alternative FE variants (Total contrib. only)
    # ------------------------------------------------------------------




    df_init = pd.read_csv(input_init).copy()
    df_init["fe_tag"] = "init"

    df_alt = pd.read_csv(input_alt).copy()
    if "fe_tag" not in df_alt.columns:
        raise SystemExit("Expected 'fe_tag' column in alternative FE results")

    df_fe = pd.concat([df_init, df_alt], ignore_index=True, sort=False)

    columns = config["columns"]  # type: ignore[assignment]
    headers = config["headers"]  # type: ignore[assignment]

    table_body = build_combined_table(df_fe, columns=columns, headers=headers).rstrip()

    tex_lines = [table_body]

    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text("\n".join(tex_lines) + "\n")

    legacy_files = [
        output_tex.with_name(f"{SPEC_BASE}_{args.variant}_ols.tex"),
        output_tex.with_name(f"{SPEC_BASE}_{args.variant}_iv.tex"),
    ]
    if args.variant == "precovid" and not config["filename_suffix"]:
        legacy_files.extend(
            [
                output_tex.with_name("user_productivity_precovid.tex"),
                output_tex.with_name("user_productivity_precovid_table.tex"),
                output_tex.with_name("user_productivity_precovid_double_panel.tex"),
            ]
        )
    if config["filename_suffix"]:
        # clean up historical suffixed variants if they exist
        legacy_files.extend(
            [
                output_tex.with_name(f"{SPEC_BASE}_{args.variant}_ols{config['filename_suffix']}.tex"),
                output_tex.with_name(f"{SPEC_BASE}_{args.variant}_iv{config['filename_suffix']}.tex"),
            ]
        )
    for old in legacy_files:
        if old.exists():
            old.unlink()

    print(f"Wrote LaTeX table to {output_tex.resolve()}")


if __name__ == "__main__":
    main()
