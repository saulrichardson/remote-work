#!/usr/bin/env python3
"""Render a five-column robustness table for non-software comparisons.

Columns shown (all using firm × user FE):
  1. Drop NAICS 5415xx firms (techfilter spec)
  2. Drop canonical tech SOC roles
  3. Drop CA/NY locations
  4. Drop Top 5 CSAs
  5. Drop Top 10 CSAs
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"

import sys

if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW
from build_baseline_table import (  # type: ignore
    PARAM_LABEL,
    PARAM_ORDER,
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
    column_format,
)

PRIMARY_OUTCOME = "total_contributions_q100"
FE_TAG = "firmXuser_yh"
OUTPUT_BASENAME = "user_productivity_precovid_nonsoftware"


@dataclass(frozen=True)
class ColumnSpec:
    label: str
    dir_template: str
    description: str

    def csv_path(self, variant: str) -> Path:
        folder = self.dir_template.format(variant=variant)
        return RESULTS_RAW / folder / "consolidated_results.csv"


COLUMN_SPECS: list[ColumnSpec] = [
    ColumnSpec(
        label=r"\makecell[c]{Drop\\NAICS}",
        dir_template="user_productivity_techfilter_{variant}_naics_software",
        description="Exclude NAICS 54151x software dev firms",
    ),
    ColumnSpec(
        label=r"\makecell[c]{Drop\\SOC}",
        dir_template="user_productivity_techfilter_{variant}_soc_strict_new",
        description="Exclude canonical tech SOC roles",
    ),
    ColumnSpec(
        label=r"\makecell[c]{Drop\\CA/NY}",
        dir_template="user_productivity_{variant}_exclude_ca_ny",
        description="Exclude CA or NY job locations",
    ),
    ColumnSpec(
        label=r"\makecell[c]{Drop\\Top 5\\CSAs}",
        dir_template="user_productivity_firmbyuser_{variant}_droptop5",
        description="Exclude firms in the top 5 CSAs",
    ),
    ColumnSpec(
        label=r"\makecell[c]{Drop\\Top 10\\CSAs}",
        dir_template="user_productivity_firmbyuser_{variant}_droptop10",
        description="Exclude firms in the top 10 CSAs",
    ),
]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_spec_frame(spec: ColumnSpec, variant: str) -> pd.DataFrame:
    csv_path = spec.csv_path(variant)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing results for {spec.label}: {csv_path}")
    df = pd.read_csv(csv_path)
    mask = df["outcome"] == PRIMARY_OUTCOME
    if "fe_tag" in df.columns:
        mask &= df["fe_tag"] == FE_TAG
    sub = df.loc[mask].copy()
    if sub.empty:
        raise RuntimeError(f"No matching rows for {spec.label} (variant={variant})")
    return sub


def subset_row(
    df: pd.DataFrame,
    *,
    model: str,
    param: str | None = None,
) -> pd.Series:
    mask = df["model_type"] == model
    if param is not None:
        mask &= df["param"] == param
    sub = df.loc[mask]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.iloc[0]


def build_panel_rows(frames: list[pd.DataFrame], model: str) -> list[str]:
    rows: list[str] = []
    indent = r"\hspace{1em}"
    for param in PARAM_ORDER:
        cells = [indent + PARAM_LABEL[param]]
        for df in frames:
            entry = subset_row(df, model=model, param=param)
            if entry.empty or pd.isna(entry.get("coef")) or pd.isna(entry.get("se")):
                cells.append("--")
            else:
                cells.append(coef_cell(entry["coef"], entry["se"], entry["pval"]))
        rows.append(" & ".join(cells) + r" \\")
    return rows


def stat_row(
    frames: list[pd.DataFrame],
    *,
    model: str,
    field: str,
    label: str,
    formatter: Callable[[float], str],
) -> str:
    values = []
    for df in frames:
        entry = subset_row(df, model=model)
        val = entry.get(field)
        if pd.isna(val):
            values.append("--")
        else:
            values.append(formatter(float(val)))
    return label + " & " + " & ".join(values) + r" \\"


def build_filter_row(specs: list[ColumnSpec]) -> str:
    return r"\textbf{Filter} & " + " & ".join(spec.label for spec in specs) + r" \\"


def build_table(frames: list[pd.DataFrame]) -> str:
    width = len(frames)
    col_fmt = column_format(width)
    headers = [spec.label for spec in COLUMN_SPECS]
    cmidrules = " ".join(rf"\cmidrule(lr){{{i}-{i}}}" for i in range(2, width + 2))
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_fmt}}}",
        TOP,
        r" & \multicolumn{" + f"{width}" + r"}{c}{Contribution Rank} \\",
        rf"\cmidrule(lr){{2-{width + 1}}}",
        " & " + " & ".join(headers) + r" \\",
        cmidrules,
        r"\textbf{Sample Filter} & " + " & ".join(f"({i})" for i in range(1, width + 1)) + r" \\",
        MID,
        rf"\multicolumn{{{width + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
        *build_panel_rows(frames, model="OLS"),
        MID,
        stat_row(
            frames,
            model="OLS",
            field="pre_mean",
            label="Pre-Covid Mean",
            formatter=lambda v: f"{v:.2f}",
        ),
        stat_row(
            frames,
            model="OLS",
            field="nobs",
            label="N",
            formatter=lambda v: f"{int(v):,}",
        ),
        MID,
        rf"\multicolumn{{{width + 1}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
        *build_panel_rows(frames, model="IV"),
        MID,
        stat_row(
            frames,
            model="IV",
            field="rkf",
            label="KP rk Wald F",
            formatter=lambda v: f"{v:.2f}",
        ),
        stat_row(
            frames,
            model="IV",
            field="nobs",
            label="N",
            formatter=lambda v: f"{int(v):,}",
        ),
        MID,
    ]

    fe_rows = [
        (r"\hspace{1em}Time", [r"$\checkmark$"] * width),
        (r"\hspace{1em}Firm", [""] * width),
        (r"\hspace{1em}Individual", [""] * width),
        (r"\hspace{1em}Firm $\times$ Individual", [r"$\checkmark$"] * width),
    ]
    active_fe_rows = [
        label + " & " + " & ".join(values) + r" \\"
        for label, values in fe_rows
        if any(value.strip() for value in values)
    ]
    if active_fe_rows:
        lines.extend(
            [
                r"\textbf{Fixed Effects} & " + " & ".join([""] * width) + r" \\",
                *active_fe_rows,
            ]
        )

    lines.extend(
        [
            BOTTOM,
            r"\end{tabular*}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=["precovid"],
        default="precovid",
        help="User panel variant (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED_TEX / f"{OUTPUT_BASENAME}.tex",
        help="Destination .tex file",
    )
    args = parser.parse_args()

    frames = [load_spec_frame(spec, args.variant) for spec in COLUMN_SPECS]
    tex = build_table(frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(tex, encoding="utf-8")
    print(f"Wrote non-software robustness table to {args.output}")


if __name__ == "__main__":
    main()
