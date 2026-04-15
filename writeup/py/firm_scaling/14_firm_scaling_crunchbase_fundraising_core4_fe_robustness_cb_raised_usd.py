#!/usr/bin/env python3
"""Build an appendix robustness table for Crunchbase fundraising (USD raised outcome).

Goal
----
Produce a 4-column appendix table using the robustness design:
  (1) Firm FE + industry×half-year shocks
  (2) Firm FE + HQ-state×half-year shocks
  (3) Firm FE + both sets of shocks
  (4) Firm FE + half-year FE, restricted to age < 20

Consumes Stata exports produced by:
  spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do

Reads:
  results/raw/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd/consolidated_results.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.py.project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file  # type: ignore

PREAMBLE_FLEX = "\\centering\n"
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"


def column_format(n_numeric: int) -> str:
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"

LB = r" \\"
INDENT = r"\hspace{1em}"

SPECNAME = "14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd"
RAW_RESULTS = RESULTS_RAW / SPECNAME / "consolidated_results.csv"
OUTPUT_TEX = (
    RESULTS_CLEANED_TEX
    / "firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex"
)

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


@dataclass(frozen=True)
class OutcomeSpec:
    outcome: str
    title: str  # Multicolumn header text
    decimals: int
    scale: float = 1.0  # divide coef/se/pre_mean by this for display


OUTCOMES: list[OutcomeSpec] = [
    OutcomeSpec("cb_raised_usd", "USD raised (mil)", decimals=2, scale=1e6),
]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def _is_missing(x: object) -> bool:
    try:
        return x is None or (isinstance(x, float) and math.isnan(x))
    except TypeError:
        return False


def coef_cell(coef: float | None, se: float | None, p: float | None, *, decimals: int, scale: float) -> str:
    if coef is None or se is None or p is None:
        return r"\makecell[c]{\textit{omitted}}"
    if _is_missing(coef) or _is_missing(se) or _is_missing(p):
        return r"\makecell[c]{\textit{omitted}}"
    if float(se) == 0:
        return r"\makecell[c]{\textit{omitted}}"

    coef_f = float(coef) / scale
    se_f = float(se) / scale
    p_f = float(p)
    return rf"\makecell[c]{{{coef_f:.{decimals}f}{stars(p_f)}\\({se_f:.{decimals}f})}}"


def load_results(path: Path = RAW_RESULTS) -> pd.DataFrame:
    require_file(
        path,
        nonempty=True,
        purpose="Stata exports for core4 FE robustness appendix (consolidated_results.csv)",
    )
    df = pd.read_csv(path)
    required = {"model_type", "fe_tag", "outcome", "param", "coef", "se", "pval", "pre_mean", "rkf", "nobs"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns in {path.name}: {sorted(missing)}")
    return df


def select_row(df: pd.DataFrame, *, fe_tag: str, model: str, outcome: str) -> pd.Series:
    mask = (
        (df["fe_tag"] == fe_tag)
        & (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["param"] == PARAM)
    )
    sub = df.loc[mask]
    if sub.empty:
        raise KeyError(f"Missing row: fe_tag={fe_tag}, model={model}, outcome={outcome}, param={PARAM}")
    if len(sub) > 1:
        raise ValueError(f"Duplicate rows: fe_tag={fe_tag}, model={model}, outcome={outcome}, param={PARAM}")
    return sub.iloc[0]


def header_lines(*, title: str) -> list[str]:
    ncols = len(FE_COLUMNS)
    numbers = " & ".join(f"({i})" for i in range(1, ncols + 1))
    col_cmidrules = " ".join(rf"\cmidrule(lr){{{j}-{j}}}" for j in range(2, ncols + 2))
    return [
        TOP,
        rf" & \multicolumn{{{ncols}}}{{c}}{{{title}}} " + LB,
        rf"\cmidrule(lr){{2-{ncols + 1}}}",
        " & " + numbers + LB,
        col_cmidrules,
        " & ".join([r"\textbf{Sample}", "", "", "", r"Age $<20$"]) + LB,
        MID,
    ]


def panel_rows(df: pd.DataFrame, *, model: str, outcome: OutcomeSpec) -> list[str]:
    cells: list[str] = []
    for fe_tag, _ in FE_COLUMNS:
        rec = select_row(df, fe_tag=fe_tag, model=model, outcome=outcome.outcome)
        cells.append(
            coef_cell(
                rec.get("coef"),
                rec.get("se"),
                rec.get("pval"),
                decimals=outcome.decimals,
                scale=outcome.scale,
            )
        )
    return [" & ".join([INDENT + PARAM_LABEL, *cells]) + LB]


def _fmt_num(val: object, *, decimals: int, scale: float) -> str:
    if _is_missing(val):
        return ""
    return f"{float(val) / scale:.{decimals}f}"


def _fmt_int(val: object) -> str:
    if _is_missing(val):
        return ""
    return f"{int(float(val)):,}"


def stat_rows_ols(df: pd.DataFrame, *, outcome: OutcomeSpec) -> list[str]:
    pre_cells: list[str] = []
    n_cells: list[str] = []
    for fe_tag, _ in FE_COLUMNS:
        rec = select_row(df, fe_tag=fe_tag, model="OLS", outcome=outcome.outcome)
        pre_cells.append(_fmt_num(rec.get("pre_mean"), decimals=outcome.decimals, scale=outcome.scale))
        n_cells.append(_fmt_int(rec.get("nobs")))
    return [
        " & ".join(["Pre-Covid Mean", *pre_cells]) + LB,
        " & ".join(["N", *n_cells]) + LB,
    ]


def stat_rows_iv(df: pd.DataFrame, *, outcome: OutcomeSpec) -> list[str]:
    kp_cells: list[str] = []
    n_cells: list[str] = []
    for fe_tag, _ in FE_COLUMNS:
        rec = select_row(df, fe_tag=fe_tag, model="IV", outcome=outcome.outcome)
        kp_cells.append(_fmt_num(rec.get("rkf"), decimals=2, scale=1.0))
        n_cells.append(_fmt_int(rec.get("nobs")))
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
        entries: list[str] = []
        for fe_tag, _ in FE_COLUMNS:
            entries.append(r"$\checkmark$" if FE_FLAGS[fe_tag].get(label, False) else "")
        lines.append(" & ".join([INDENT + label, *entries]) + LB)
    return lines


def build_table(df: pd.DataFrame, *, outcome: OutcomeSpec) -> str:
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(FE_COLUMNS))}}}",
    ]
    lines.extend(header_lines(title=outcome.title))
    lines.append(r"\addlinespace[2pt]")

    panels = (("OLS", "Panel A: OLS"), ("IV", "Panel B: IV"))
    for idx, (model, panel_label) in enumerate(panels):
        lines.append(
            rf"\multicolumn{{{len(FE_COLUMNS)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")
        lines.extend(panel_rows(df, model=model, outcome=outcome))
        lines.append(MID)
        if model == "OLS":
            lines.extend(stat_rows_ols(df, outcome=outcome))
        else:
            lines.extend(stat_rows_iv(df, outcome=outcome))
        if idx == 0:
            lines.append(MID)

    lines.append(MID)
    lines.extend(fe_block())
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=RESULTS_CLEANED_TEX,
        help="Destination directory for TeX fragments.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    df = load_results()

    ensure_dir(args.out_dir)
    written: list[Path] = []
    for outcome in OUTCOMES:
        out_path = OUTPUT_TEX
        out_path.write_text(build_table(df, outcome=outcome), encoding="utf-8")
        written.append(out_path)

    print("Wrote core4 FE-robustness appendix table:")
    for p in written:
        print(" -", p)


if __name__ == "__main__":
    main()
