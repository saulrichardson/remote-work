#!/usr/bin/env python3
"""Create the firm-scaling table for per-employee geography ratios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

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

PARAM_ORDER = ("var3", "var5")
PARAM_LABEL = {
    **BASE_PARAM_LABEL,
    "var3": BASE_PARAM_LABEL.get(
        "var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"
    ),
    "var5": BASE_PARAM_LABEL.get(
        "var5",
        r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    ),
}

COLUMN_LABELS = {
    "states_per_employee": r"\makecell[c]{\# States /\\Employee}",
    "msas_per_employee": r"\makecell[c]{\# MSAs /\\Employee}",
    "locations_per_employee": r"\makecell[c]{\# Locations /\\Employee}",
    # Imputed columns deliberately inherit the legacy labels to keep writeups concise.
    "states_imputed_per_employee": r"\makecell[c]{\# States /\\Employee}",
    "msas_imputed_per_employee": r"\makecell[c]{\# MSAs /\\Employee}",
    "locations_imputed_per_employee": r"\makecell[c]{\# Locations /\\Employee}",
}

DEFAULT_STATE = "states_imputed_per_employee"
DEFAULT_MSA = "msas_imputed_per_employee"
DEFAULT_LOCATION = "locations_imputed_per_employee"

COLUMNS: Sequence[tuple[str, str]] = (
    (DEFAULT_STATE, COLUMN_LABELS[DEFAULT_STATE]),
    (DEFAULT_MSA, COLUMN_LABELS[DEFAULT_MSA]),
    (DEFAULT_LOCATION, COLUMN_LABELS[DEFAULT_LOCATION]),
)


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def header_lines(num_cols: int) -> list[str]:
    labels = " & ".join(label for _, label in COLUMNS)
    numbers = " & ".join(f"({i})" for i in range(1, num_cols + 1))
    cmidrules = " ".join(
        rf"\cmidrule(lr){{{col}-{col}}}" for col in range(2, num_cols + 2)
    )
    return [
        TOP,
        r" & " + labels + LB,
        cmidrules,
        " & " + numbers + LB,
        MID,
    ]


def load_results() -> pd.DataFrame:
    path = RESULTS_RAW / "firm_scaling_locations_per_employee" / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def select_row(
    df: pd.DataFrame,
    *,
    outcome: str,
    model: str,
    param: str | None = None,
    field: str | None = None,
) -> pd.Series | float | None:
    mask = (df["outcome"] == outcome) & (df["model_type"] == model)
    if param:
        mask &= df["param"] == param
    sub = df.loc[mask]
    if sub.empty:
        return None
    if field:
        return sub.iloc[0][field]
    return sub.iloc[0]


def coef_cell(rec: pd.Series | None) -> str:
    if rec is None:
        return "--"
    coef, se, pval = rec["coef"], rec["se"], rec["pval"]
    return rf"\makecell[c]{{{coef:.3f}{stars(pval)}\\({se:.3f})}}"


def param_rows(df: pd.DataFrame, *, model: str) -> list[str]:
    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = [INDENT + PARAM_LABEL[param]]
        for outcome, _ in COLUMNS:
            rec = select_row(df, outcome=outcome, model=model, param=param)
            cells.append(coef_cell(rec))
        rows.append(" & ".join(cells) + LB)
    return rows


def stats_rows(df: pd.DataFrame, *, model: str) -> list[str]:
    lines: list[str] = []
    entries = []
    for outcome, _ in COLUMNS:
        val = select_row(df, outcome=outcome, model=model, field="pre_mean")
        entries.append("" if val is None or pd.isna(val) else f"{val:.3f}")
    lines.append(" & ".join(["Pre-Covid Mean", *entries]) + LB)

    if model == "IV":
        entries = []
        for outcome, _ in COLUMNS:
            val = select_row(df, outcome=outcome, model=model, field="rkf")
            entries.append("" if val is None or pd.isna(val) else f"{val:.2f}")
        lines.append(" & ".join(["KP rk Wald F", *entries]) + LB)

    entries = []
    for outcome, _ in COLUMNS:
        val = select_row(df, outcome=outcome, model=model, field="nobs")
        entries.append("" if val is None or pd.isna(val) else f"{int(val):,}")
    lines.append(" & ".join(["N", *entries]) + LB)
    return lines


def build_table(df: pd.DataFrame) -> str:
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(COLUMNS))}}}",
    ]
    lines.extend(header_lines(len(COLUMNS)))
    lines.append(r"\addlinespace[2pt]")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(
            rf"\multicolumn{{{len(COLUMNS)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")
        lines.extend(param_rows(df, model=model))
        lines.append(MID)
        lines.extend(stats_rows(df, model=model))
        if panel_label == "Panel A: OLS":
            lines.append(MID)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_location_ratios.tex",
        help="Destination TeX file",
    )
    parser.add_argument(
        "--state-outcome",
        choices=("states_per_employee", "states_imputed_per_employee"),
        default=DEFAULT_STATE,
        help="Outcome name for the first (state) column",
    )
    parser.add_argument(
        "--msa-outcome",
        choices=("msas_per_employee", "msas_imputed_per_employee"),
        default=DEFAULT_MSA,
        help="Outcome name for the second (MSA) column",
    )
    parser.add_argument(
        "--location-outcome",
        choices=("locations_per_employee", "locations_imputed_per_employee"),
        default=DEFAULT_LOCATION,
        help="Outcome name for the third (location) column",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global COLUMNS
    COLUMNS = (
        (args.state_outcome, COLUMN_LABELS[args.state_outcome]),
        (args.msa_outcome, COLUMN_LABELS[args.msa_outcome]),
        (args.location_outcome, COLUMN_LABELS[args.location_outcome]),
    )
    df = load_results()
    ensure_dir(args.output.parent)
    tex = build_table(df)
    args.output.write_text(tex)
    print(f"Wrote location-ratio table → {args.output}")


if __name__ == "__main__":
    main()
