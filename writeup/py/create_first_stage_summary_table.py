#!/usr/bin/env python3
"""Build a consolidated first-stage table for the mini writeup."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

USER_BASE_PATH = PROJECT_ROOT / "results" / "raw" / "user_productivity_precovid" / "first_stage.csv"
USER_ALT_PATH = (
    PROJECT_ROOT
    / "results"
    / "raw"
    / "user_productivity_alternative_fe_precovid"
    / "first_stage_fstats.csv"
)
FIRM_PATH = PROJECT_ROOT / "results" / "raw" / "firm_scaling" / "first_stage.csv"

OUTPUT_PATH = PROJECT_ROOT / "results" / "cleaned" / "first_stage_summary.tex"
TARGET_OUTCOME = "total_contributions_q100"

PARAMS = ["var6", "var7", "var4"]

COL_TITLES = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

PARAM_LABEL = {
    "var6": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) $",
    "var7": r"$ \text{Teleworkable} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

# Significance star cutoffs used by stars()
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def load_user_tables() -> dict[str, pd.DataFrame]:
    if not USER_BASE_PATH.exists():
        raise FileNotFoundError(USER_BASE_PATH)
    if not USER_ALT_PATH.exists():
        raise FileNotFoundError(USER_ALT_PATH)

    base = pd.read_csv(USER_BASE_PATH)
    alt = pd.read_csv(USER_ALT_PATH)
    alt = alt[(alt["fe_tag"] == "firmbyuseryh") & (alt["outcome"] == TARGET_OUTCOME)]
    if alt.empty:
        raise ValueError("Alternative FE file lacks firmbyuseryh rows for total_contributions_q100")
    return {"baseline": base, "firmby": alt}


def load_firm_table() -> pd.DataFrame:
    if not FIRM_PATH.exists():
        raise FileNotFoundError(FIRM_PATH)
    return pd.read_csv(FIRM_PATH)


def get_row(df: pd.DataFrame, endo: str, param: str) -> pd.Series:
    match = df[(df["endovar"] == endo) & (df["param"] == param)]
    if match.empty:
        raise KeyError(f"Missing row: endovar={endo}, param={param}")
    return match.iloc[0]



def build_lines(user_tables: dict[str, pd.DataFrame], firm_df: pd.DataFrame) -> list[str]:
    columns = [
        ("var3", "baseline"),
        ("var3", "firmby"),
        ("var5", "baseline"),
        ("var5", "firmby"),
    ]
    dash = "--"
    indent = r"\hspace{1em}"
    row_end = " \\\\"  # single row terminator

    lines: list[str] = []

    lines.append("% Auto-generated – do *not* edit by hand")
    lines.append(r"{\centering")

    # Use tabularx so the four numeric columns share width evenly
    colspec = r"l" + r"*{" + str(len(columns)) + r"}{>{\centering\arraybackslash}X}"
    lines.append(r"\begin{tabularx}{\linewidth}{" + colspec + "}")
    lines.append(r"\toprule")
    lines.append(
        " & "
        + r"\multicolumn{2}{c}{" + COL_TITLES["var3"] + "} & "
        + r"\multicolumn{2}{c}{" + COL_TITLES["var5"] + "}"
        + row_end
    )
    lines.append(r"\cmidrule(lr){2-3}")
    lines.append(r"\cmidrule(lr){4-5}")
    lines.append(r"\midrule")
    lines.append("\\multicolumn{5}{l}{\\textbf{\\uline{User-level}}}\\\\")

    for param in PARAMS:
        row = [f"{indent}{PARAM_LABEL.get(param, param)}"]
        for endo, spec in columns:
            entry = get_row(user_tables[spec], endo, param)
            row.append(cell(entry.coef, entry.se, entry.pval))
        lines.append(" & ".join(row) + row_end)

    lines.append(r"\midrule")
    lines.append(" & ".join(["\\textbf{Fixed Effects}", "", "", "", ""]) + row_end)

    fe_rows = [
        ("Time FE", [True, True, True, True]),
        ("Firm FE", [True, False, True, False]),
        ("User FE", [True, False, True, False]),
        ("Firm \\ensuremath{\\times} User FE", [False, True, False, True]),
    ]

    for label, checks in fe_rows:
        row = [f"{indent}{label}"]
        for idx, _ in enumerate(columns):
            row.append(r"$\checkmark$" if checks[idx] else "")
        lines.append(" & ".join(row) + row_end)

    lines.append(r"\midrule")

    user_summary = [
        ("Partial F", lambda e: e.partialF, lambda v: dash if pd.isna(v) else f"{v:.2f}"),
        ("KP rk Wald F", lambda e: e.rkf, lambda v: dash if pd.isna(v) else f"{v:.2f}"),
        ("N", lambda e: e.nobs, lambda v: dash if pd.isna(v) else f"{int(v):,}"),
    ]

    for label, accessor, formatter in user_summary:
        row = [label]
        for endo, spec in columns:
            entry = get_row(user_tables[spec], endo, PARAMS[0])
            row.append(formatter(accessor(entry)))
        lines.append(" & ".join(row) + row_end)

    lines.append(r"\midrule")
    lines.append("\\multicolumn{5}{l}{\\textbf{\\uline{Firm-level}}}\\\\")
    lines.append(r"\addlinespace[2pt]")

    for param in PARAMS:
        row = [f"{indent}{PARAM_LABEL.get(param, param)}"]
        left = get_row(firm_df, "var3", param)
        right = get_row(firm_df, "var5", param)
        for endo, spec in columns:
            if spec != "baseline":
                row.append(dash)
            elif endo == "var3":
                row.append(cell(left.coef, left.se, left.pval))
            else:
                row.append(cell(right.coef, right.se, right.pval))
        lines.append(" & ".join(row) + row_end)

    lines.append(r"\midrule")
    lines.append(" & ".join(["\\textbf{Fixed Effects}", "", "", "", ""]) + row_end)

    firm_fe_rows = [
        ("Time FE", True, True),
        ("Firm FE", True, True),
    ]

    for label, has_var3, has_var5 in firm_fe_rows:
        row = [f"{indent}{label}"]
        for endo, spec in columns:
            if spec != "baseline":
                row.append("")
            elif endo == "var3" and has_var3:
                row.append(r"$\checkmark$")
            elif endo == "var5" and has_var5:
                row.append(r"$\checkmark$")
            else:
                row.append("")
        lines.append(" & ".join(row) + row_end)

    lines.append(r"\midrule")

    firm_base_var3 = get_row(firm_df, "var3", PARAMS[0])
    firm_base_var5 = get_row(firm_df, "var5", PARAMS[0])

    firm_summary = [
        ("Partial F", firm_base_var3.partialF, firm_base_var5.partialF, lambda v: dash if pd.isna(v) else f"{v:.2f}"),
        ("KP rk Wald F", firm_base_var3.rkf, firm_base_var5.rkf, lambda v: dash if pd.isna(v) else f"{v:.2f}"),
        ("N", firm_base_var3.nobs, firm_base_var5.nobs, lambda v: dash if pd.isna(v) else f"{int(v):,}"),
    ]

    for label, var3_val, var5_val, formatter in firm_summary:
        row = [label]
        for endo, spec in columns:
            if spec != "baseline":
                row.append(dash)
            elif endo == "var3":
                row.append(formatter(var3_val))
            else:
                row.append(formatter(var5_val))
        lines.append(" & ".join(row) + row_end)

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabularx}")
    lines.append(r"}")

    return lines


def main() -> None:
    user_tables = load_user_tables()
    firm_df = load_firm_table()
    lines = build_lines(user_tables, firm_df)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote LaTeX table to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
