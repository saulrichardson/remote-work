#!/usr/bin/env python3
"""Build a 3-column robustness table: firm FE + industry/HQ-state half-year shocks.

Inputs (from Stata spec):
  results/raw/firm_scaling_industry_hqstate_shocks/consolidated_results.csv

Output:
  results/cleaned/tex/firm_scaling_industry_hqstate_shocks.tex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))
SCRIPTS_DIR = HERE.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
from user_productivity.build_baseline_table import (  # type: ignore
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
    column_format,
    PARAM_LABEL as BASE_PARAM_LABEL,
)

LB = r" \\"
INDENT = r"\hspace{1em}"

OUTCOME = "growth_rate_we"
OUTCOME_LABEL = r"Growth"
PARAM_ORDER = ("var3", "var5")
PARAM_LABEL = {
    **BASE_PARAM_LABEL,
    "var3": BASE_PARAM_LABEL.get("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
    "var5": BASE_PARAM_LABEL.get(
        "var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"
    ),
}


FE_COLUMNS: list[tuple[str, str]] = [
    ("ind_yh", r"\makecell[c]{Industry\\ $\times$ Half-Year}"),
    ("state_yh", r"\makecell[c]{HQ State\\ $\times$ Half-Year}"),
    ("both_yh", r"\makecell[c]{Industry + HQ State\\ $\times$ Half-Year}"),
]

FE_FLAGS: dict[str, dict[str, bool]] = {
    "ind_yh": {
        "Firm": True,
        "Industry $\\times$ Half-Year": True,
        "HQ State $\\times$ Half-Year": False,
    },
    "state_yh": {
        "Firm": True,
        "Industry $\\times$ Half-Year": False,
        "HQ State $\\times$ Half-Year": True,
    },
    "both_yh": {
        "Firm": True,
        "Industry $\\times$ Half-Year": True,
        "HQ State $\\times$ Half-Year": True,
    },
}


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_results() -> pd.DataFrame:
    path = RESULTS_RAW / "firm_scaling_industry_hqstate_shocks" / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    required = {"model_type", "fe_tag", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "nobs"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns in {path.name}: {sorted(missing)}")
    return df


def select_row(
    df: pd.DataFrame,
    *,
    fe_tag: str,
    model: str,
    outcome: str,
    param: str,
) -> pd.Series:
    mask = (
        (df["fe_tag"] == fe_tag)
        & (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["param"] == param)
    )
    sub = df.loc[mask]
    if sub.empty:
        raise KeyError(f"Missing row: fe_tag={fe_tag}, model={model}, outcome={outcome}, param={param}")
    if len(sub) > 1:
        raise ValueError(f"Duplicate rows: fe_tag={fe_tag}, model={model}, outcome={outcome}, param={param}")
    return sub.iloc[0]


def header_lines() -> list[str]:
    ncols = len(FE_COLUMNS)
    numbers = " & ".join(f"({i})" for i in range(1, ncols + 1))
    return [
        TOP,
        rf" & \multicolumn{{{ncols}}}{{c}}{{{OUTCOME_LABEL}}} " + LB,
        rf"\cmidrule(lr){{2-{ncols + 1}}}",
        " & " + numbers + LB,
        MID,
    ]


def param_rows(df: pd.DataFrame, *, model: str) -> list[str]:
    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = []
        for fe_tag, _ in FE_COLUMNS:
            rec = select_row(df, fe_tag=fe_tag, model=model, outcome=OUTCOME, param=param)
            cells.append(coef_cell(rec["coef"], rec["se"], rec["pval"]))
        rows.append(" & ".join([INDENT + PARAM_LABEL[param], *cells]) + LB)
    return rows


def stat_rows(df: pd.DataFrame, *, model: str, include_kp: bool) -> list[str]:
    lines: list[str] = []
    for field, label, is_int in (
        ("pre_mean", "Pre-Covid Mean", False),
        ("nobs", "N", True),
    ):
        entries = []
        for fe_tag, _ in FE_COLUMNS:
            rec = select_row(df, fe_tag=fe_tag, model=model, outcome=OUTCOME, param="var3")
            val = rec[field]
            if pd.isna(val):
                entries.append("--")
            else:
                entries.append(f"{int(val):,}" if is_int else f"{float(val):.2f}")
        lines.append(" & ".join([label, *entries]) + LB)

    if include_kp:
        kp_entries = []
        for fe_tag, _ in FE_COLUMNS:
            rec = select_row(df, fe_tag=fe_tag, model=model, outcome=OUTCOME, param="var3")
            val = rec["rkf"]
            kp_entries.append("--" if pd.isna(val) else f"{float(val):.2f}")
        lines.insert(-1, " & ".join(["KP rk Wald F", *kp_entries]) + LB)

    return lines


def fe_block() -> list[str]:
    labels = [
        "Firm",
        "Industry $\\times$ Half-Year",
        "HQ State $\\times$ Half-Year",
    ]
    lines = [r"\textbf{Fixed Effects} & " + " & ".join([""] * len(FE_COLUMNS)) + LB]
    for label in labels:
        entries = []
        for fe_tag, _ in FE_COLUMNS:
            entries.append(r"$\checkmark$" if FE_FLAGS[fe_tag].get(label, False) else "")
        lines.append(" & ".join([INDENT + label, *entries]) + LB)
    return lines


def build_table(df: pd.DataFrame) -> str:
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(FE_COLUMNS))}}}",
    ]
    lines.extend(header_lines())
    lines.append(r"\addlinespace[2pt]")

    panels = (("OLS", False, "Panel A: OLS"), ("IV", True, "Panel B: IV"))
    for idx, (model, include_kp, panel_label) in enumerate(panels):
        lines.append(
            rf"\multicolumn{{{len(FE_COLUMNS)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")
        lines.extend(param_rows(df, model=model))
        lines.append(MID)
        lines.extend(stat_rows(df, model=model, include_kp=include_kp))
        if idx == 0:
            lines.append(MID)

    lines.append(MID)
    lines.extend(fe_block())
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_industry_hqstate_shocks.tex",
        help="Destination TeX file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = load_results()
    df = df.loc[df["outcome"] == OUTCOME].copy()

    ensure_dir(args.output.parent)
    tex = build_table(df)
    args.output.write_text(tex)
    print(f"Wrote firm shocks table → {args.output}")


if __name__ == "__main__":
    main()
