#!/usr/bin/env python3
"""Render startup-size robustness tables (OLS + IV) across size cutoffs."""

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
SCRIPTS_DIR = HERE.parent  # writeup/py
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir
from user_productivity.build_baseline_table import (
    PARAM_LABEL as USER_PARAM_LABEL,
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
    column_format,
)

LB = " \\\\"  # line break
INDENT = r"\hspace{1em}"
CUTOFFS: tuple[int, ...] = (50, 100, 150, 200, 500)

PARAM_ORDER: tuple[str, ...] = ("var3", "var5")
PARAM_LABEL = {
    **USER_PARAM_LABEL,
    "var3": USER_PARAM_LABEL.get("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
    "var5": USER_PARAM_LABEL.get(
        "var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup (size)} $"
    ),
}

OUTCOMES = [
    ("user", "total_contributions_q100", "Total Contribution Rank"),
    ("user", "restricted_contributions_q100", "Restricted Contribution Rank"),
    ("firm", "growth_rate_we", "Firm Growth Rate"),
    ("firm", "join_rate_we", "Firm Join Rate"),
    ("firm", "leave_rate_we", "Firm Leave Rate"),
]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_results(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["cutoff"] = df["cutoff"].astype(int)
    return df


def value(df: pd.DataFrame, *, cutoff: int, outcome: str, model: str, param: str | None = None, field: str | None = None) -> pd.Series:
    mask = (df["cutoff"] == cutoff) & (df["outcome"] == outcome) & (df["model_type"] == model)
    if param:
        mask &= df["param"] == param
    row = df.loc[mask]
    if row.empty:
        return pd.Series(dtype=float)
    if field:
        return pd.Series(row.iloc[0][field])
    return row.iloc[0]


def header_lines(label: str) -> list[str]:
    cols = len(CUTOFFS)
    numbering = " & ".join(f"({i})" for i in range(1, cols + 1))
    cmidrules = " ".join(rf"\cmidrule(lr){{{i}-{i}}}" for i in range(2, cols + 2))
    return [
        TOP,
        r" & \multicolumn{" + f"{cols}" + r"}{c}{" + label + r"} " + LB,
        r"\cmidrule(lr){2-" + f"{cols + 1}" + r"}",
        " & " + " & ".join(rf"$\leq {c}$" for c in CUTOFFS) + LB,
        cmidrules,
        r"\textbf{Startup Size Cutoff} & " + numbering + LB,
        MID,
    ]


def param_rows(df: pd.DataFrame, *, outcome: str, model: str) -> list[str]:
    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = []
        for cut in CUTOFFS:
            rec = value(df, cutoff=cut, outcome=outcome, model=model, param=param)
            if rec.empty:
                cells.append("--")
            else:
                cells.append(coef_cell(rec["coef"], rec["se"], rec["pval"]))
        rows.append(" & ".join([INDENT + PARAM_LABEL[param], *cells]) + LB)
    return rows


def stat_rows(df: pd.DataFrame, *, outcome: str, model: str, include_kp: bool) -> list[str]:
    lines: list[str] = []
    for field, label in (("pre_mean", "Pre-Covid Mean"), ("nobs", "N")):
        entries = []
        for cut in CUTOFFS:
            val = value(df, cutoff=cut, outcome=outcome, model=model, field=field)
            if val.empty or pd.isna(val.iloc[0]):
                entries.append("--")
            else:
                entries.append(f"{int(round(val.iloc[0])):,}" if field == "nobs" else f"{val.iloc[0]:,.2f}")
        lines.append(" & ".join([label, *entries]) + LB)
    if include_kp:
        kp_entries = []
        for cut in CUTOFFS:
            val = value(df, cutoff=cut, outcome=outcome, model=model, field="rkf")
            kp_entries.append("--" if val.empty or pd.isna(val.iloc[0]) else f"{val.iloc[0]:,.2f}")
        lines.insert(-1, " & ".join(["KP rk Wald F", *kp_entries]) + LB)
    return lines


def build_table(*, label: str, dataset: str, outcome: str, user_df: pd.DataFrame, firm_df: pd.DataFrame) -> str:
    df = user_df if dataset == "user" else firm_df
    lines: list[str] = [PREAMBLE_FLEX, rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(CUTOFFS))}}}"]
    lines.extend(header_lines(label))
    lines.append(r"\addlinespace[2pt]")

    for idx, (model, include_kp) in enumerate((("OLS", False), ("IV", True))):
        panel_label = "Panel A: OLS" if idx == 0 else "Panel B: IV"
        lines.append(rf"\multicolumn{{{len(CUTOFFS)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}")
        lines.append(r"\addlinespace[2pt]")
        lines.extend(param_rows(df, outcome=outcome, model=model))
        lines.append(MID)
        lines.extend(stat_rows(df, outcome=outcome, model=model, include_kp=include_kp))
        if idx == 0:
            lines.append(MID)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-csv",
        type=Path,
        default=RESULTS_RAW / "user_productivity_size_cutoff_sweep_precovid" / "consolidated_results.csv",
        help="User size cutoff sweep CSV.",
    )
    parser.add_argument(
        "--firm-csv",
        type=Path,
        default=RESULTS_RAW / "firm_scaling_size_cutoff_sweep" / "consolidated_results.csv",
        help="Firm size cutoff sweep CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_CLEANED_TEX,
        help="Directory for the LaTeX tables.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dir(args.output_dir)

    user_df = load_results(args.user_csv)
    firm_df = load_results(args.firm_csv)

    for dataset, outcome, label in OUTCOMES:
        tex = build_table(label=label, dataset=dataset, outcome=outcome, user_df=user_df, firm_df=firm_df)
        output_path = args.output_dir / f"startup_size_cutoff_{outcome}.tex"
        output_path.write_text(tex, encoding="utf-8")
        print(f"Wrote {label} table to {output_path}")


if __name__ == "__main__":
    main()
