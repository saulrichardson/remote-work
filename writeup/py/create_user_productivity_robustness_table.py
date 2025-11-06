#!/usr/bin/env python3
"""Format robustness variants of the user-productivity specification."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_FINAL_TEX, RESULTS_RAW

from create_user_productivity_table import (  # type: ignore
    BOTTOM,
    MID,
    PARAM_LABEL,
    PARAM_ORDER,
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    column_format,
)

LB = r" \\"  # LaTeX line break


@dataclass(frozen=True)
class RobustnessSpec:
    tag: str
    label: str
    filters: dict[str, bool]


ROBUSTNESS_SPECS: list[RobustnessSpec] = [
    RobustnessSpec(
        tag="no_tech_industry",
        label="Drop Tech Industry",
        filters={
            "Drop Tech Industry": True,
            "Drop SOC Core": False,
            "Only CA/NY": False,
            "Exclude CA/NY": False,
        },
    ),
    RobustnessSpec(
        tag="no_tech_soc",
        label="Drop SOC Core",
        filters={
            "Drop Tech Industry": False,
            "Drop SOC Core": True,
            "Only CA/NY": False,
            "Exclude CA/NY": False,
        },
    ),
    RobustnessSpec(
        tag="only_ca_ny",
        label="Only CA/NY",
        filters={
            "Drop Tech Industry": False,
            "Drop SOC Core": False,
            "Only CA/NY": True,
            "Exclude CA/NY": False,
        },
    ),
    RobustnessSpec(
        tag="exclude_ca_ny",
        label="Exclude CA/NY",
        filters={
            "Drop Tech Industry": False,
            "Drop SOC Core": False,
            "Only CA/NY": False,
            "Exclude CA/NY": True,
        },
    ),
]

FILTER_LABELS = [
    "Drop Tech Industry",
    "Drop SOC Core",
    "Only CA/NY",
    "Exclude CA/NY",
]

PRIMARY_OUTCOME = "total_contributions_q100"
FE_SEQUENCE = ["firm_user_yh", "firmXuser_yh"]

FE_FIELDS = [
    ("time", "Time"),
    ("firm", "Firm"),
    ("individual", "Individual"),
    ("pair", r"Firm $\times$ Individual"),
]

FE_MARKERS = {
    "firm_user_yh": {
        "time": True,
        "firm": True,
        "individual": True,
        "pair": False,
    },
    "firmXuser_yh": {
        "time": True,
        "firm": False,
        "individual": False,
        "pair": True,
    },
}

OUTPUT_PREFIX = "user_productivity_precovid_robustness_part"


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_results(spec: RobustnessSpec) -> pd.DataFrame:
    csv_path = RESULTS_RAW / f"user_productivity_precovid_{spec.tag}" / "consolidated_results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing results: {csv_path}")
    df = pd.read_csv(csv_path)
    if "fe_tag" not in df.columns:
        raise RuntimeError(f"Expected 'fe_tag' column in {csv_path}")
    df["robustness_tag"] = spec.tag
    return df


def subset_row(
    df: pd.DataFrame,
    *,
    model: str,
    robustness: str,
    fe_tag: str,
    param: str | None = None,
) -> pd.Series:
    mask = (
        (df["model_type"] == model)
        & (df["outcome"] == PRIMARY_OUTCOME)
        & (df["robustness_tag"] == robustness)
        & (df["fe_tag"] == fe_tag)
    )
    if param is not None:
        mask &= df["param"] == param
    sub = df[mask]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.iloc[0]


def build_header_numbers(specs: Sequence[RobustnessSpec]) -> str:
    total_cols = len(specs) * len(FE_SEQUENCE)
    return " & " + " & ".join(f"({i})" for i in range(1, total_cols + 1)) + LB


def build_outcome_header(specs: Sequence[RobustnessSpec]) -> tuple[str, str]:
    total_cols = len(specs) * len(FE_SEQUENCE)
    header = r" & \multicolumn{" + f"{total_cols}" + r"}{c}{Contribution Rank} " + LB
    cmid = rf"\cmidrule(lr){{2-{total_cols + 1}}}"
    return header, cmid


def panel_rows(
    df: pd.DataFrame,
    *,
    model: str,
    specs: Sequence[RobustnessSpec],
    include_kp: bool,
    include_pre_mean: bool,
) -> list[str]:
    lines: list[str] = []
    indent = r"\hspace{1em}"
    for param in PARAM_ORDER:
        row = [indent + PARAM_LABEL[param]]
        for spec in specs:
            for fe_tag in FE_SEQUENCE:
                sub = subset_row(df, model=model, robustness=spec.tag, fe_tag=fe_tag, param=param)
                if sub.empty or pd.isna(sub.get("coef")) or pd.isna(sub.get("se")):
                    row.append("--")
                else:
                    row.append(coef_cell(sub["coef"], sub["se"], sub["pval"]))
        lines.append(" & ".join(row) + LB)

    lines.append(MID)
    if include_pre_mean:
        row = ["Pre-Covid Mean"]
        for spec in specs:
            for fe_tag in FE_SEQUENCE:
                sub = subset_row(df, model=model, robustness=spec.tag, fe_tag=fe_tag)
                value = sub.get("pre_mean") if not sub.empty else float("nan")
                row.append("--" if pd.isna(value) else f"{value:.2f}")
        lines.append(" & ".join(row) + LB)

    if include_kp:
        row = ["KP rk Wald F"]
        for spec in specs:
            for fe_tag in FE_SEQUENCE:
                sub = subset_row(df, model=model, robustness=spec.tag, fe_tag=fe_tag)
                value = sub.get("rkf") if not sub.empty else float("nan")
                row.append("--" if pd.isna(value) else f"{value:.2f}")
        lines.append(" & ".join(row) + LB)

    row = ["N"]
    for spec in specs:
        for fe_tag in FE_SEQUENCE:
            sub = subset_row(df, model=model, robustness=spec.tag, fe_tag=fe_tag)
            value = sub.get("nobs") if not sub.empty else float("nan")
            row.append("--" if pd.isna(value) else f"{int(value):,}")
    lines.append(" & ".join(row) + LB)

    return lines


def build_filter_rows(specs: Sequence[RobustnessSpec]) -> list[str]:
    row_count = len(specs) * len(FE_SEQUENCE)
    rows = [r"\textbf{Sample Filters}" + " & " + " & ".join([""] * row_count) + LB]
    indent = r"\hspace{1em}"
    for label in FILTER_LABELS:
        row = [indent + label]
        for spec in specs:
            mark = r"$\checkmark$" if spec.filters.get(label, False) else ""
            row.extend([mark] * len(FE_SEQUENCE))
        rows.append(" & ".join(row) + LB)
    return rows


def build_fe_block(column_tags: Sequence[str]) -> list[str]:
    rows = [r"\textbf{Fixed Effects}" + " & " + " & ".join([""] * len(column_tags)) + LB]
    indent = r"\hspace{1em}"
    for field_key, label in FE_FIELDS:
        line = [indent + label]
        for tag in column_tags:
            mark = FE_MARKERS.get(tag, {}).get(field_key, False)
            line.append(r"$\checkmark$" if mark else "")
        rows.append(" & ".join(line) + LB)
    return rows


def build_tables(df: pd.DataFrame, specs: Sequence[RobustnessSpec]) -> list[str]:
    blocks: list[str] = []
    chunk = 2  # number of robustness specs (=> 4 columns) per table
    for start in range(0, len(specs), chunk):
        slice_specs = specs[start : start + chunk]
        numbers = build_header_numbers(slice_specs)
        outcome_header, outcome_cmid = build_outcome_header(slice_specs)
        col_fmt = column_format(len(slice_specs) * len(FE_SEQUENCE))
        panel_a = panel_rows(df, model="OLS", specs=slice_specs, include_kp=False, include_pre_mean=True)
        panel_b = panel_rows(df, model="IV", specs=slice_specs, include_kp=True, include_pre_mean=False)

        column_tags: list[str] = []
        for _spec in slice_specs:
            column_tags.extend(FE_SEQUENCE)
        fe_block = build_fe_block(column_tags)
        filter_block = build_filter_rows(slice_specs)
        width = len(column_tags) + 1

        lines = [
            rf"\begin{{tabular*}}{{\linewidth}}{{{col_fmt}}}",
            TOP,
            outcome_header,
            outcome_cmid,
            numbers,
            MID,
            rf"\multicolumn{{{width}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
            r"\addlinespace[2pt]",
            *panel_a,
            MID,
            rf"\multicolumn{{{width}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
            r"\addlinespace[2pt]",
            *panel_b,
            MID,
            *fe_block,
            MID,
            *filter_block,
            BOTTOM,
            r"\end{tabular*}",
        ]
        blocks.append(PREAMBLE_FLEX + "\n".join(lines))

    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Create robustness tables for user productivity spec")
    parser.add_argument(
        "--output-prefix",
        default=OUTPUT_PREFIX,
        help="Base filename prefix written to results/final/tex (chunk index appended)",
    )
    args = parser.parse_args()

    frames = [load_results(spec) for spec in ROBUSTNESS_SPECS]
    df_all = pd.concat(frames, ignore_index=True, sort=False)

    tables = build_tables(df_all, ROBUSTNESS_SPECS)

    for idx, tex in enumerate(tables, start=1):
        out_path = RESULTS_FINAL_TEX / f"{args.output_prefix}{idx}.tex"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(tex + "\n")
        print(f"Wrote robustness table to {out_path}")


if __name__ == "__main__":
    main()
