#!/usr/bin/env python3
"""Build a 4-column robustness table for Crunchbase fundraising (USD raised rank).

Consumes Stata exports produced by:
  spec/stata/firm_scaling_crunchbase_fundraising_rank_age20_fe_robustness.do

Reads:
  results/raw/firm_scaling_crunchbase_fundraising_rank_age20_fe_robustness/consolidated_results.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_rank_age20_fe_robustness.tex
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
)

LB = r" \\"
INDENT = r"\hspace{1em}"

SPECNAME = "firm_scaling_crunchbase_fundraising_rank_age20_fe_robustness"
RAW_RESULTS = RESULTS_RAW / SPECNAME / "consolidated_results.csv"
OUT_TEX = RESULTS_CLEANED_TEX / f"{SPECNAME}.tex"

OUTCOME = "cb_raised_usd_rank"
OUTCOME_LABEL = r"USD raised rank"
PARAM = "var3"
PARAM_LABEL = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"

FE_COLUMNS: list[tuple[str, str]] = [
    ("ind_yh", ""),
    ("state_yh", ""),
    ("both_yh", ""),
    ("age_lt20", ""),
]

FE_FLAGS: dict[str, dict[str, bool]] = {
    "age_lt20": {
        "Firm": True,
        "Time": True,
        "Industry $\\times$ Half-Year": False,
        "HQ State $\\times$ Half-Year": False,
    },
    "ind_yh": {
        "Firm": True,
        "Time": False,
        "Industry $\\times$ Half-Year": True,
        "HQ State $\\times$ Half-Year": False,
    },
    "state_yh": {
        "Firm": True,
        "Time": False,
        "Industry $\\times$ Half-Year": False,
        "HQ State $\\times$ Half-Year": True,
    },
    "both_yh": {
        "Firm": True,
        "Time": False,
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


def load_results(path: Path = RAW_RESULTS) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing raw results: {path}. "
            f"Run: do spec/stata/{SPECNAME}.do"
        )
    df = pd.read_csv(path)
    required = {"model_type", "fe_tag", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "nobs"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns in {path.name}: {sorted(missing)}")
    return df


def select_row(df: pd.DataFrame, *, fe_tag: str, model: str) -> pd.Series:
    mask = (
        (df["fe_tag"] == fe_tag)
        & (df["model_type"] == model)
        & (df["outcome"] == OUTCOME)
        & (df["param"] == PARAM)
    )
    sub = df.loc[mask]
    if sub.empty:
        raise KeyError(f"Missing row: fe_tag={fe_tag}, model={model}, outcome={OUTCOME}, param={PARAM}")
    if len(sub) > 1:
        raise ValueError(f"Duplicate rows: fe_tag={fe_tag}, model={model}, outcome={OUTCOME}, param={PARAM}")
    return sub.iloc[0]


def header_lines() -> list[str]:
    ncols = len(FE_COLUMNS)
    numbers = " & ".join(f"({i})" for i in range(1, ncols + 1))
    col_cmidrules = " ".join(rf"\cmidrule(lr){{{j}-{j}}}" for j in range(2, ncols + 2))
    return [
        TOP,
        rf" & \multicolumn{{{ncols}}}{{c}}{{{OUTCOME_LABEL}}} " + LB,
        rf"\cmidrule(lr){{2-{ncols + 1}}}",
        " & " + numbers + LB,
        col_cmidrules,
        " & ".join([r"\textbf{Sample}", "", "", "", r"Age $<20$"]) + LB,
        MID,
    ]


def panel_rows(df: pd.DataFrame, *, model: str) -> list[str]:
    cells = []
    for fe_tag, _ in FE_COLUMNS:
        rec = select_row(df, fe_tag=fe_tag, model=model)
        cells.append(coef_cell(float(rec["coef"]), float(rec["se"]), float(rec["pval"])))
    return [" & ".join([INDENT + PARAM_LABEL, *cells]) + LB]


def stat_rows_ols(df: pd.DataFrame) -> list[str]:
    pre_cells = []
    n_cells = []
    for fe_tag, _ in FE_COLUMNS:
        rec = select_row(df, fe_tag=fe_tag, model="OLS")
        pre_cells.append(f"{float(rec['pre_mean']):.2f}")
        n_cells.append(f"{int(rec['nobs']):,}")
    return [
        " & ".join(["Pre-Covid Mean", *pre_cells]) + LB,
        " & ".join(["N", *n_cells]) + LB,
    ]


def stat_rows_iv(df: pd.DataFrame) -> list[str]:
    kp_cells = []
    n_cells = []
    for fe_tag, _ in FE_COLUMNS:
        rec = select_row(df, fe_tag=fe_tag, model="IV")
        kp_cells.append(f"{float(rec['rkf']):.2f}")
        n_cells.append(f"{int(rec['nobs']):,}")
    return [
        " & ".join(["KP rk Wald F", *kp_cells]) + LB,
        " & ".join(["N", *n_cells]) + LB,
    ]


def fe_block() -> list[str]:
    labels = [
        "Firm",
        "Time",
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

    panels = (("OLS", "Panel A: OLS"), ("IV", "Panel B: IV"))
    for idx, (model, panel_label) in enumerate(panels):
        lines.append(
            rf"\multicolumn{{{len(FE_COLUMNS)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")
        lines.extend(panel_rows(df, model=model))
        lines.append(MID)
        if model == "OLS":
            lines.extend(stat_rows_ols(df))
        else:
            lines.extend(stat_rows_iv(df))
        if idx == 0:
            lines.append(MID)

    lines.append(MID)
    lines.extend(fe_block())
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT_TEX, help="Destination TeX file.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = load_results()
    df = df.loc[df["outcome"] == OUTCOME].copy()

    ensure_dir(args.out.parent)
    args.out.write_text(build_table(df), encoding="utf-8")
    print(f"Wrote Crunchbase fundraising rank robustness table → {args.out}")


if __name__ == "__main__":
    main()
