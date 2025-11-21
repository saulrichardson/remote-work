#!/usr/bin/env python3
"""Generate wage tables (GitHub vs. LinkedIn samples) with Panel A/B layout.

The script mirrors the formatting of Table 2 for user productivity but swaps
in wage outcomes (log salary).  The companion Stata script
``spec/stata/user_wage_fe_variants.do`` writes a consolidated CSV with an
``fe_tag`` column covering four FE variants:

    user_firm_yh         – firm + user + time FE
    userfirm_yh          – firm × user + time FE
    userfirm_yh_title    – firm × user + time FE + occupation title FE
    userfirm_yh_title_location – match FE + job title + job location FE
    userfirm_yh_title_msa – match FE + job title + job MSA FE

Panel A reports OLS, Panel B the IV estimates (including the KP statistic).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

RAW_DIR = RESULTS_RAW
OUTPUT_DIR = RESULTS_CLEANED_TEX

COLUMN_SPECS = [
    {
        "tag": "user_firm_yh",
        "label": "Baseline: Time + Firm + Individual FE",
        "fe": {
            "time": True,
            "firm": True,
            "individual": True,
            "match": False,
            "title": False,
            "job_location": False,
            "msa_location": False,
        },
    },
    {
        "tag": "userfirm_yh",
        "label": "Match: Time + Firm×Individual FE",
        "fe": {
            "time": True,
            "firm": False,
            "individual": False,
            "match": True,
            "title": False,
            "job_location": False,
            "msa_location": False,
        },
    },
    {
        "tag": "userfirm_yh_title",
        "label": "Match + Job Title FE",
        "fe": {
            "time": True,
            "firm": False,
            "individual": False,
            "match": True,
            "title": True,
            "job_location": False,
            "msa_location": False,
        },
    },
]

PARAM_ORDER = [
    ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
    ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
]

FE_ROWS = [
    ("Time", "time"),
    ("Firm", "firm"),
    ("Individual", "individual"),
    (r"Firm $\times$ Individual", "match"),
    ("Title", "title"),
]

INDENT = r"\hspace{1em}"


def stars(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def format_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(pval)}\\({se:.2f})}}"


def load_results(variant: str) -> pd.DataFrame:
    path = RAW_DIR / f"user_wage_fe_variants_{variant}" / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing wage results: {path}")
    df = pd.read_csv(path)
    if "fe_tag" not in df.columns:
        raise RuntimeError(
            f"Expected 'fe_tag' column in {path}. Did the Stata export include FE variants?"
        )
    return df


def collect_cells(
    df: pd.DataFrame,
    model: str,
    params: Iterable[tuple[str, str]],
) -> list[list[str]]:
    rows: list[list[str]] = []
    for param, label in params:
        row = [f"{INDENT}{label}"]
        for column in COLUMN_SPECS:
            sub = df[
                (df["model_type"] == model)
                & (df["fe_tag"] == column["tag"])
                & (df["param"] == param)
            ]
            if sub.empty:
                row.append("")
            else:
                coef, se, pval = sub.iloc[0][["coef", "se", "pval"]]
                row.append(format_cell(float(coef), float(se), float(pval)))
        rows.append(row)
    return rows


def stat_row(
    df: pd.DataFrame,
    model: str,
    field: str,
    label: str,
    formatter,
) -> list[str]:
    values: list[str] = [label]
    for column in COLUMN_SPECS:
        sub = df[(df["model_type"] == model) & (df["fe_tag"] == column["tag"])]
        if sub.empty:
            values.append("")
            continue
        value = sub.iloc[0][field]
        if pd.isna(value):
            values.append("")
        else:
            values.append(formatter(value))
    return values


def build_table(df: pd.DataFrame) -> str:
    header_nums = " & ".join(f"({i})" for i in range(1, len(COLUMN_SPECS) + 1))
    col_spec = r"@{}l" + r"@{\extracolsep{\fill}}c" * len(COLUMN_SPECS) + r"@{}"

    lines: list[str] = [
        r"\centering",
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_spec}}}",
        r"\toprule",
        rf" & \multicolumn{{{len(COLUMN_SPECS)}}}{{c}}{{Log salary}} \\",
        rf"\cmidrule(lr){{2-{len(COLUMN_SPECS)+1}}}",
        " & " + header_nums + r" \\",
        r"\midrule",
        r"\multicolumn{" + str(len(COLUMN_SPECS) + 1) + r"}{@{}l}{\textbf{\uline{Panel A: OLS}}} \\",
        r"\addlinespace[2pt]",
    ]

    for row in collect_cells(df, "OLS", PARAM_ORDER):
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    lines.append(" & ".join(stat_row(df, "OLS", "pre_mean", "Pre-Covid Mean", lambda x: f"{float(x):.2f}")) + r" \\")
    lines.append(" & ".join(stat_row(df, "OLS", "nobs", "N", lambda x: f"{int(x):,}")) + r" \\")
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{" + str(len(COLUMN_SPECS) + 1) + r"}{@{}l}{\textbf{\uline{Panel B: IV}}} \\")
    lines.append(r"\addlinespace[2pt]")

    for row in collect_cells(df, "IV", PARAM_ORDER):
        lines.append(" & ".join(row) + r" \\")

    lines.append(r"\midrule")
    lines.append(" & ".join(stat_row(df, "IV", "rkf", "KP rk Wald F", lambda x: f"{float(x):.2f}")) + r" \\")
    lines.append(" & ".join(stat_row(df, "IV", "nobs", "N", lambda x: f"{int(x):,}")) + r" \\")
    lines.append(r"\midrule")

    # Fixed effects block
    fe_header = ["\\textbf{Fixed Effects}"] + [""] * len(COLUMN_SPECS)
    lines.append(" & ".join(fe_header) + r" \\")
    for label, key in FE_ROWS:
        marks = [
            r"$\checkmark$" if column["fe"].get(key, False) else ""
            for column in COLUMN_SPECS
        ]
        lines.append(r"\hspace{1em}" + label + " & " + " & ".join(marks) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create wage regression tables with FE variants")
    parser.add_argument(
        "--variant",
        choices=["precovid", "unbalanced", "balanced", "balanced_pre"],
        default="precovid",
        help="User panel variant / sample (default: %(default)s)",
    )
    args = parser.parse_args()

    df = load_results(args.variant)
    # Restrict to log salary outcome
    df = df[df["outcome"] == "log_salary"].copy()
    if df.empty:
        raise RuntimeError("No log_salary results found in wage output.")

    table_body = build_table(df)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_name = f"user_wage_fe_variants_{args.variant}_log_salary.tex"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text(table_body, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
