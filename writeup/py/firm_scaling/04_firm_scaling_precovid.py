#!/usr/bin/env python3
"""Build the active firm-scaling table family and emit both paper fragments."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from src.py.project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

RAW_DIR = RESULTS_RAW / "04_firm_scaling_precovid"
FINAL_TEX_DIR = RESULTS_CLEANED_TEX
PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
HEADER_OVERRIDES = {
    "Postings": r"\makecell[c]{\rule{0pt}{0.9em}Postings}",
    "Hires/Postings": r"\makecell[c]{\rule{0pt}{0.9em}Hires/\\Posting}",
    "Any Postings": r"\makecell[c]{\rule{0pt}{0.9em}Any\\Postings}",
}


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def column_format(n_numeric: int) -> str:
    parts = ["@{}l"]
    parts.extend([r"@{\extracolsep{\fill}}c"] * n_numeric)
    parts.append("@{}")
    return "".join(parts)


def format_label(text: str) -> str:
    text = text.replace("&", r"\&")
    if text in HEADER_OVERRIDES:
        return HEADER_OVERRIDES[text]
    if " " in text:
        first, rest = text.split(" ", 1)
        return rf"\makecell[c]{{{first}\\{rest}}}"
    return text


def build_header_block(
    columns: Sequence[tuple[str, str, str]], start_index: int
) -> tuple[str, str, str]:
    groups: list[tuple[str, int]] = []
    idx = 0
    while idx < len(columns):
        label = columns[idx][2]
        span = 1
        while idx + span < len(columns) and columns[idx + span][2] == label:
            span += 1
        groups.append((label, span))
        idx += span

    header_cells = [""]
    for label, span in groups:
        formatted = format_label(label)
        if span == 1:
            header_cells.append(formatted)
        else:
            header_cells.append(rf"\multicolumn{{{span}}}{{c}}{{{formatted}}}")
    header_groups = " & ".join(header_cells) + r" \\"

    cmidrules = []
    col_start = 2
    for _, span in groups:
        col_end = col_start + span - 1
        cmidrules.append(rf"\cmidrule(lr){{{col_start}-{col_end}}}")
        col_start = col_end + 1

    header_nums = " & " + " & ".join(
        f"({i})" for i in range(start_index, start_index + len(columns))
    ) + r" \\"
    return header_groups, "\n".join(cmidrules), header_nums


def coef_cell(row: pd.Series) -> str:
    coef, se, pval = row[["coef", "se", "pval"]]
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def fetch_entry(df: pd.DataFrame, model: str, outcome: str, tag: str, param: str) -> pd.Series | None:
    sub = df[
        (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["fe_tag"] == tag)
        & (df["param"] == param)
    ].head(1)
    return None if sub.empty else sub.iloc[0]


def stat_value(df: pd.DataFrame, model: str, outcome: str, tag: str, field: str, fmt: str) -> str:
    sub = df[
        (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["fe_tag"] == tag)
    ].head(1)
    if sub.empty:
        return ""
    value = sub.iloc[0].get(field)
    return "" if pd.isna(value) else fmt.format(value)


def build_panel(df: pd.DataFrame, model: str, columns: Sequence[tuple[str, str, str]]) -> list[str]:
    indent = r"\hspace{1em}"
    lines: list[str] = []
    for param in PARAM_ORDER:
        row_cells = [indent + PARAM_LABEL[param]]
        for outcome, tag, _ in columns:
            entry = fetch_entry(df, model, outcome, tag, param)
            row_cells.append(coef_cell(entry) if entry is not None else "--")
        lines.append(" & ".join(row_cells) + r" \\")
    return lines


def build_stats_rows(df: pd.DataFrame, columns: Sequence[tuple[str, str, str]], *, model: str) -> list[str]:
    labels = []
    if model == "OLS":
        labels.append(("Pre-Covid Mean", "pre_mean", "{:.2f}"))
    if model == "IV":
        labels.append(("KP rk Wald F", "rkf", "{:.2f}"))
    labels.append(("N", "nobs", "{:,}"))
    rows: list[str] = []
    for label, field, fmt in labels:
        values = [stat_value(df, model, outcome, tag, field, fmt) for outcome, tag, _ in columns]
        rows.append(" & ".join([label, *values]) + r" \\")
    return rows


def fixed_effect_rows(num_cols: int) -> list[str]:
    checks = " & ".join([r"$\checkmark$"] * num_cols)
    indent = r"\hspace{1em}"
    return [
        r"\textbf{Fixed Effects} & " + " & ".join([""] * num_cols) + r" \\",
        indent + r"Time & " + checks + r" \\",
        indent + r"Firm & " + checks + r" \\",
    ]


def build_table(df: pd.DataFrame, columns: Sequence[tuple[str, str, str]], *, start_index: int) -> str:
    num_cols = len(columns)
    col_fmt = column_format(num_cols)
    header_groups, cmidrule_block, header_nums = build_header_block(columns, start_index)
    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_fmt}}}",
        r"\toprule",
        header_groups,
        cmidrule_block,
        header_nums,
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
        r"\end{tabular*}",
    ]
    return "\n".join(lines) + "\n"


def load_cols1_4_data() -> pd.DataFrame:
    baseline = pd.read_csv(RAW_DIR / "growth_baseline_main_effect" / "consolidated_results.csv")
    baseline["fe_tag"] = "baseline_main_effect"
    interacted = pd.read_csv(RAW_DIR / "growth_interacted_columns" / "consolidated_results.csv")
    interacted["fe_tag"] = "firm_time_fe"
    return pd.concat([baseline, interacted], ignore_index=True, sort=False)


def load_cols5_6_data() -> pd.DataFrame:
    vacancy = pd.read_csv(RAW_DIR / "vacancy_interacted_columns" / "consolidated_results.csv")
    vacancy["fe_tag"] = "firm_time_fe"
    return vacancy


def write_cols1_4(df: pd.DataFrame) -> Path:
    columns = [
        ("growth_rate_we", "baseline_main_effect", "Growth"),
        ("growth_rate_we", "firm_time_fe", "Growth"),
        ("join_rate_we", "firm_time_fe", "Join"),
        ("leave_rate_we", "firm_time_fe", "Leave"),
    ]
    output = FINAL_TEX_DIR / "firm_scaling_precovid_cols1_4.tex"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_table(df, columns, start_index=1))
    return output


def write_cols5_6(df: pd.DataFrame) -> Path:
    columns = [
        ("vacancies_thousands", "firm_time_fe", "Postings"),
        ("hires_to_vacancies_winsor95_min3", "firm_time_fe", "Hires/Postings"),
        ("any_vacancy", "firm_time_fe", "Any Postings"),
    ]
    output = FINAL_TEX_DIR / "firm_scaling_precovid_cols5_6.tex"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_table(df, columns, start_index=1))
    return output


def main() -> None:
    cols1_4_output = write_cols1_4(load_cols1_4_data())
    cols5_6_output = write_cols5_6(load_cols5_6_data())
    print(f"Wrote {cols1_4_output}")
    print(f"Wrote {cols5_6_output}")


if __name__ == "__main__":
    main()
