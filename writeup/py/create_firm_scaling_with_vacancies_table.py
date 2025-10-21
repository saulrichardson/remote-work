#!/usr/bin/env python3
"""Create firm scaling tables augmented with vacancy outcomes."""

from __future__ import annotations

import argparse
from pathlib import Path
import textwrap

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw"
CLEAN_DIR = PROJECT_ROOT / "results" / "cleaned"

SPEC_INIT = "firm_scaling_initial"
SPEC_BASE = "firm_scaling"
SPEC_VAC = "firm_scaling_vacancy_outcomes_htv2_95"

PARAM_ORDER = ["var3", "var5", "var4"]
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOME_LABEL = {
    "growth_rate_we": r"\makecell[c]{Growth\\(wins.)}",
    "join_rate_we": r"\makecell[c]{Join\\(wins.)}",
    "leave_rate_we": r"\makecell[c]{Leave\\(wins.)}",
    "vacancies_thousands": r"\makecell[c]{Vacancies}",
    "hires_to_vacancies_winsor95_min2": r"\makecell[c]{Hires/Vacancies}",
}

COL_CONFIG = [
    ("growth_rate_we", "init"),
    ("growth_rate_we", "fyh"),
    ("join_rate_we", "fyh"),
    ("leave_rate_we", "fyh"),
    ("vacancies_thousands", "vac"),
    ("hires_to_vacancies_winsor95_min2", "vac"),
]

FIRM_FE_INCLUDED = {"init": True, "fyh": True, "vac": True}
TIME_FE_INCLUDED = {"init": True, "fyh": True, "vac": True}

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def column_format(n_numeric: int) -> str:
    return "l" + "c" * n_numeric


def build_table(df: pd.DataFrame, *, model: str) -> str:
    include_kp = model == "IV"

    col_tags = [tag for _, tag in COL_CONFIG]
    header_nums = " & ".join(["", *[f"({i})" for i in range(1, len(COL_CONFIG) + 1)]]) + ' \\'
    header_outcomes = " & ".join(["", *[OUTCOME_LABEL[o] for o, _ in COL_CONFIG]]) + ' \\'

    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for outcome, tag in COL_CONFIG:
            mask = (
                (df["model_type"] == model)
                & (df["outcome"] == outcome)
                & (df["fe_tag"] == tag)
                & (df["param"] == param)
            )
            if mask.any():
                row = df.loc[mask].iloc[0]
                coef, se, pval = row["coef"], row["se"], row["pval"]
                cells.append(f"\\makecell[c]{{{coef:.2f}{stars(pval)}\\\\({se:.2f})}}")
            else:
                cells.append("")
        rows.append(" & ".join(cells) + ' \\')
    coef_block = "\n".join(rows)

    def indicator_row(label: str, mapping: dict[str, bool]) -> str:
        marks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in col_tags]
        return " & ".join([label, *marks]) + ' \\'

    indicator_block = "\n".join(
        [
            indicator_row("Time FE", TIME_FE_INCLUDED),
            indicator_row("Firm FE", FIRM_FE_INCLUDED),
        ]
    )

    def stat_row(label: str, field: str, fmt: str | None) -> str:
        vals: list[str] = []
        for outcome, tag in COL_CONFIG:
            mask = (
                (df["model_type"] == model)
                & (df["outcome"] == outcome)
                & (df["fe_tag"] == tag)
            )
            sub = df.loc[mask]
            if sub.empty or pd.isna(sub.iloc[0].get(field, None)):
                vals.append("")
            else:
                value = sub.iloc[0][field]
                vals.append(fmt.format(value) if fmt else str(value))
        return " & ".join([label, *vals]) + ' \\'

    summary_rows = [stat_row("Pre-Covid Mean", "pre_mean", "{:.2f}")]
    if include_kp:
        summary_rows.append(stat_row("KP rk Wald F", "rkf", "{:.2f}"))
    summary_rows.append(stat_row("N", "nobs", "{:,}"))
    summary_block = "\n".join(summary_rows)

    col_fmt = column_format(len(COL_CONFIG))
    lines = [
        rf"\begin{{tabular}}{{{col_fmt}}}",
        "\\toprule",
        header_nums,
        "\\midrule",
        header_outcomes,
        "\\midrule",
        coef_block,
        "\\midrule",
        indicator_block,
        "\\midrule",
        summary_block,
        "\\bottomrule",
        "\\end{tabular}",
    ]

    return "\n".join(lines)


def load_data() -> pd.DataFrame:
    init_path = RAW_DIR / SPEC_INIT / "consolidated_results.csv"
    base_path = RAW_DIR / SPEC_BASE / "consolidated_results.csv"
    vac_path = RAW_DIR / SPEC_VAC / "consolidated_results.csv"

    if not init_path.exists():
        raise FileNotFoundError(init_path)
    if not base_path.exists():
        raise FileNotFoundError(base_path)
    if not vac_path.exists():
        raise FileNotFoundError(vac_path)

    df_init = pd.read_csv(init_path)
    df_init["fe_tag"] = "init"

    df_base = pd.read_csv(base_path)
    df_base["fe_tag"] = "fyh"

    df_vac = pd.read_csv(vac_path)
    df_vac["fe_tag"] = "vac"

    return pd.concat([df_init, df_base, df_vac], ignore_index=True, sort=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create firm scaling table with vacancy outcomes")
    parser.add_argument("--model-type", choices=["ols", "iv"], default="ols")
    args = parser.parse_args()

    model = "IV" if args.model_type.lower() == "iv" else "OLS"
    df = load_data()

    table_body = build_table(df, model=model)

    caption = f"Firm Scaling with Vacancy Outcomes — {model}"
    label = f"tab:firm_scaling_vacancy_{model.lower()}"
    output_name = f"firm_scaling_with_vacancies_{args.model_type.lower()}.tex"
    output_path = CLEAN_DIR / output_name

    tex_lines = [
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        table_body,
        r"\end{table}",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {output_path}")


if __name__ == "__main__":
    main()
