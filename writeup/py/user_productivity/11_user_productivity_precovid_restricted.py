#!/usr/bin/env python3
"""Build asset 11: user_productivity_precovid_restricted.tex."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.py.project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

PREAMBLE_FLEX = "\\centering\n"
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
TABLE_WIDTH = r"\linewidth"
TABLE_ENV = "tabular*"
PARAM_ORDER = ["var3", "var5"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}
FIRM_FE_INCLUDED = {"baseline_main_effect": True, "separate_fe": True}
INDIVIDUAL_FE_INCLUDED = {"baseline_main_effect": True, "separate_fe": True}
TIME_FE_INCLUDED = {"baseline_main_effect": True, "separate_fe": True, "match_fe": True}
FIRMINDEX_FE_INCLUDED = {"match_fe": True}

OUTCOME_CONFIG = {
    "columns": [
        ("restricted_contributions_q100", "baseline_main_effect"),
        ("restricted_contributions_q100", "separate_fe"),
        ("restricted_contributions_q100", "match_fe"),
        ("restricted_contributions_we", "match_fe"),
    ],
    "headers": {
        "restricted_contributions_q100": r"Contribution Rank",
        "restricted_contributions_we": r"Total",
    },
}


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def column_format(n_numeric: int) -> str:
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"


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
    return header_nums, header_groups, "\n".join(cmidrules)


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
            cells.append("--")
            continue
        value = sub.iloc[0].get(field)
        cells.append("--" if pd.isna(value) else fmt.format(value))
    return " & ".join([label, *cells]) + r" \\"


def _panel_rows(
    df: pd.DataFrame,
    model: str,
    *,
    columns: list[tuple[str, str]],
    column_tags: list[str],
    panel_label: str | None,
    include_kp: bool,
    include_pre_mean: bool,
    trailing_midrule: bool,
) -> list[str]:
    lines: list[str] = []
    if panel_label is not None:
        lines.append(
            rf"\multicolumn{{{len(column_tags)+1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel {panel_label}: {model}}}}}}} \\"
        )
        lines.append(r"\addlinespace[2pt]")

    indent = r"\hspace{1em}"
    for param in PARAM_ORDER:
        row = [indent + PARAM_LABEL[param]]
        for outcome, tag in columns:
            sub = df[
                (df["model_type"] == model)
                & (df["outcome"] == outcome)
                & (df["fe_tag"] == tag)
                & (df["param"] == param)
            ].head(1)
            if sub.empty:
                row.append("--")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                row.append("--" if pd.isna(coef) or pd.isna(se) else cell(coef, se, pval))
        lines.append(" & ".join(row) + r" \\")

    lines.append(MID)
    if include_pre_mean:
        lines.append(_stat_row(df, model, columns, "Pre-Covid Mean", "pre_mean", "{:.2f}"))
    if include_kp:
        lines.append(_stat_row(df, model, columns, "KP rk Wald F", "rkf", "{:.2f}"))
    lines.append(_stat_row(df, model, columns, "N", "nobs", "{:,}"))
    if trailing_midrule:
        lines.append(MID)
    return lines


def build_fe_rows(column_tags: list[str]) -> list[str]:
    def marks(mapping: dict[str, bool]) -> list[str]:
        return [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in column_tags]

    indent = r"\hspace{1em}"
    rows = [r"\textbf{Fixed Effects} & " + " & ".join([""] * len(column_tags)) + r" \\"]
    row_defs = [
        ("Half-year", TIME_FE_INCLUDED),
        ("Firm", FIRM_FE_INCLUDED),
        ("Individual", INDIVIDUAL_FE_INCLUDED),
        (r"Firm $\times$ Individual", FIRMINDEX_FE_INCLUDED),
    ]
    for label, mapping in row_defs:
        marks_row = marks(mapping)
        if any(marks_row):
            rows.append(" & ".join([indent + label, *marks_row]) + r" \\")
    return rows


def build_combined_table(
    df: pd.DataFrame,
    *,
    columns: list[tuple[str, str]],
    headers: dict[str, str],
) -> str:
    column_tags = [tag for _, tag in columns]
    header_nums, header_groups, cmidrule_line = _build_headers(columns, headers)
    col_fmt = column_format(len(columns))

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
    fe_block = build_fe_rows(column_tags)
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
    return PREAMBLE_FLEX + "\n".join(lines)


def load_results() -> pd.DataFrame:
    root = RESULTS_RAW / "11_user_productivity_precovid_restricted"
    baseline_path = root / "baseline_main_effect" / "consolidated_results.csv"
    interacted_path = root / "interacted_columns" / "consolidated_results.csv"
    df_baseline = pd.read_csv(baseline_path)
    df_baseline["fe_tag"] = "baseline_main_effect"
    df_interacted = pd.read_csv(interacted_path)
    return pd.concat([df_baseline, df_interacted], ignore_index=True, sort=False)


def main() -> None:
    df = load_results()
    tex = build_combined_table(
        df,
        columns=OUTCOME_CONFIG["columns"],
        headers=OUTCOME_CONFIG["headers"],
    )
    out_path = RESULTS_CLEANED_TEX / "user_productivity_precovid_restricted.tex"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
