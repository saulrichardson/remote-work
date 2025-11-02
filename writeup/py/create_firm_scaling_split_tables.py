#!/usr/bin/env python3
"""Create split firm-scaling tables (columns 1–4 and columns 5–8).

The original ``create_firm_scaling_vacancies_styled_table.py`` produces a
single six-column table.  This companion script keeps the same styling but
emits two separate tables so they can be positioned independently in the
write-up.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

HERE = Path(__file__).resolve().parent
PY_DIR = HERE.parents[1] / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_FINAL_TEX, RESULTS_RAW

RAW_DIR = RESULTS_RAW
FINAL_TEX_DIR = RESULTS_FINAL_TEX

PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def column_format(n_numeric: int) -> str:
    pad = r"@{\hspace{4pt}}"
    body = (pad + r">{\centering\arraybackslash}X" + pad) * n_numeric
    return "l" + body


def load_data() -> pd.DataFrame:
    init = pd.read_csv(RAW_DIR / "firm_scaling_initial" / "consolidated_results.csv")
    init["fe_tag"] = "init"

    base = pd.read_csv(RAW_DIR / "firm_scaling" / "consolidated_results.csv")
    base["fe_tag"] = "fyh"

    vac = pd.read_csv(RAW_DIR / "firm_scaling_vacancy_outcomes_htv2_95" / "consolidated_results.csv")
    vac["fe_tag"] = "vac"

    return pd.concat([init, base, vac], ignore_index=True, sort=False)


def coef_cell(row: pd.Series) -> str:
    coef, se, pval = row[["coef", "se", "pval"]]
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def fetch_entry(
    df: pd.DataFrame,
    model: str,
    outcome: str,
    tag: str,
    param: str,
) -> pd.Series | None:
    sub = df[
        (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["fe_tag"] == tag)
        & (df["param"] == param)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def stat_value(
    df: pd.DataFrame,
    model: str,
    outcome: str,
    tag: str,
    field: str,
    fmt: str,
) -> str:
    sub = df[
        (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["fe_tag"] == tag)
    ].head(1)
    if sub.empty:
        return ""
    value = sub.iloc[0].get(field)
    if pd.isna(value):
        return ""
    return fmt.format(value)


def build_panel(
    df: pd.DataFrame,
    model: str,
    columns: Sequence[tuple[str, str, str]],
) -> list[str]:
    INDENT = r"\hspace{1em}"
    lines: list[str] = []
    for param in PARAM_ORDER:
        row_cells = [INDENT + PARAM_LABEL[param]]
        for outcome, tag, _ in columns:
            entry = fetch_entry(df, model, outcome, tag, param)
            row_cells.append(coef_cell(entry) if entry is not None else "--")
        lines.append(" & ".join(row_cells) + r" \\")
    return lines


def build_stats_rows(
    df: pd.DataFrame,
    columns: Sequence[tuple[str, str, str]],
    *,
    model: str,
) -> list[str]:
    labels = []
    if model == "OLS":
        labels.append(("Pre-Covid Mean", "pre_mean", "{:.2f}"))
    if model == "IV":
        labels.append(("KP rk Wald F", "rkf", "{:.2f}"))
    labels.append(("N", "nobs", "{:,}"))

    rows: list[str] = []
    for label, field, fmt in labels:
        values = [
            stat_value(df, model, outcome, tag, field, fmt)
            for outcome, tag, _ in columns
        ]
        rows.append(" & ".join([label, *values]) + r" \\")
    return rows


def fixed_effect_rows(num_cols: int) -> list[str]:
    checks = " & ".join([r"$\checkmark$"] * num_cols)
    INDENT = r"\hspace{1em}"
    return [
        r"\textbf{Fixed Effects} & " + " & ".join([""] * num_cols) + r" \\",
        INDENT + r"Time & " + checks + r" \\",
        INDENT + r"Firm & " + checks + r" \\",
    ]


def build_table(
    df: pd.DataFrame,
    columns: Sequence[tuple[str, str, str]],
    *,
    start_index: int,
) -> str:
    num_cols = len(columns)
    col_fmt = column_format(num_cols)
    header_nums = " & ".join(
        [""] + [f"({i})" for i in range(start_index, start_index + num_cols)]
    ) + r" \\"
    header_labels = " & ".join([""] + [label for _, _, label in columns]) + r" \\"

    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabularx}}{{\linewidth}}{{{col_fmt}}}",
        r"\toprule",
        header_nums,
        r"\midrule",
        header_labels,
        r"\midrule",
        rf"\multicolumn{{{num_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
        *build_panel(df, "OLS", columns),
        r"\midrule",
        *build_stats_rows(df, columns, model="OLS"),
        r"\midrule",
        rf"\multicolumn{{{num_cols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
        *build_panel(df, "IV", columns),
        r"\midrule",
        *build_stats_rows(df, columns, model="IV"),
        r"\midrule",
        *fixed_effect_rows(num_cols),
        r"\bottomrule",
        r"\end{tabularx}",
    ]
    return "\n".join(lines) + "\n"


def write_table(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"Wrote {path}")


def main() -> None:
    df = load_data()

    col_config = [
        ("growth_rate_we", "init", "Growth"),
        ("growth_rate_we", "fyh", "Growth"),
        ("join_rate_we", "fyh", "Join"),
        ("leave_rate_we", "fyh", "Leave"),
        ("vacancies_thousands", "vac", "Job Postings"),
        ("log_vacancies", "vac", "Log Job Postings"),
        ("hires_to_vacancies_winsor95_min3", "vac", "Hires/Job Postings"),
        ("any_vacancy", "vac", "Any Job Postings"),
    ]

    first_block = col_config[:4]
    second_block = col_config[4:]

    table1 = build_table(df, first_block, start_index=1)
    table2 = build_table(df, second_block, start_index=1)

    write_table(FINAL_TEX_DIR / "firm_scaling_precovid_cols1_4.tex", table1)
    write_table(FINAL_TEX_DIR / "firm_scaling_precovid_cols5_6.tex", table2)


if __name__ == "__main__":
    main()
