#!/usr/bin/env python3
"""Format the user-productivity results after dropping top CSAs."""

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

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
from build_baseline_table import (  # type: ignore
    PARAM_LABEL as USER_PARAM_LABEL,
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
    column_format,
)

LB = r" \\"
INDENT = r"\hspace{1em}"
PARAM_ORDER: tuple[str, ...] = ("var3", "var5")
PARAM_LABEL = {
    **USER_PARAM_LABEL,
    "var3": USER_PARAM_LABEL.get(
        "var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"
    ),
    "var5": USER_PARAM_LABEL.get(
        "var5",
        r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    ),
}

SCENARIOS: dict[str, list[tuple[str, str]]] = {
    "drop": [
        ("precovid", "Full Sample"),
        ("precovid_droptop5", "Drop CSAs Ranked 1–5"),
        ("precovid_droptop14", "Drop CSAs Ranked 1–14"),
    ],
    "keep": [
        ("precovid_keeptop5", "Keep CSAs Ranked 1–5"),
        ("precovid_keeptop6_14", "Keep CSAs Ranked 6–14"),
    ],
}

FE_FLAGS = [
    ("Time", True),
    ("Firm", True),
    ("Individual", True),
    ("Firm $\\times$ Individual", False),
]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def load_variant(tag: str, csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    df = pd.read_csv(csv_path)
    df["variant"] = tag
    return df


def combine_variants(
    *,
    results_root: Path,
    entries: Iterable[tuple[str, str]],
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    frames = []
    columns: list[tuple[str, str]] = []
    for tag, label in entries:
        csv = results_root / f"user_productivity_{tag}" / "consolidated_results.csv"
        frames.append(load_variant(tag, csv))
        columns.append((tag, label))
    return pd.concat(frames, ignore_index=True), columns


def select_row(
    df: pd.DataFrame,
    *,
    variant: str,
    outcome: str,
    model: str,
    param: str | None = None,
    field: str | None = None,
) -> pd.Series:
    mask = (df["variant"] == variant) & (df["outcome"] == outcome) & (df["model_type"] == model)
    if param:
        mask &= df["param"] == param
    subset = df.loc[mask]
    if subset.empty:
        return pd.Series(dtype=float)
    if field:
        return pd.Series(subset.iloc[0][field])
    return subset.iloc[0]


def _two_line_label(label: str) -> str:
    words = label.split()
    if len(words) <= 1:
        return label
    split_idx = len(words) // 2
    first = " ".join(words[:split_idx])
    second = " ".join(words[split_idx:])
    return rf"\makecell[c]{{{first}\\ {second}}}"


def header_lines(columns: list[tuple[str, str]]) -> list[str]:
    n_col = len(columns)
    numbering = " & ".join(f"({i})" for i in range(1, n_col + 1))
    labels = " & ".join(_two_line_label(label) for _, label in columns)
    return [
        TOP,
        r" & " + labels + LB,
        r"\cmidrule(lr){2-" + f"{n_col + 1}" + r"}",
        " & " + numbering + LB,
        MID,
    ]


def param_section(
    df: pd.DataFrame,
    *,
    columns: list[tuple[str, str]],
    outcome: str,
    model: str,
) -> list[str]:
    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = []
        for variant, _ in columns:
            rec = select_row(
                df,
                variant=variant,
                outcome=outcome,
                model=model,
                param=param,
            )
            if rec.empty:
                cells.append("--")
            else:
                cells.append(coef_cell(rec["coef"], rec["se"], rec["pval"]))
        rows.append(" & ".join([INDENT + PARAM_LABEL[param], *cells]) + LB)
    return rows


def stat_section(
    df: pd.DataFrame,
    *,
    columns: list[tuple[str, str]],
    outcome: str,
    model: str,
    include_kp: bool,
) -> list[str]:
    lines: list[str] = []
    for field, label in (("pre_mean", "Pre-Covid Mean"), ("nobs", "N")):
        entries: list[str] = []
        for variant, _ in columns:
            val = select_row(
                df,
                variant=variant,
                outcome=outcome,
                model=model,
                field=field,
            )
            if val.empty or pd.isna(val.iloc[0]):
                entries.append("--")
            else:
                if field == "nobs":
                    entries.append(f"{int(round(val.iloc[0])):,}")
                else:
                    entries.append(f"{val.iloc[0]:,.2f}")
        lines.append(" & ".join([label, *entries]) + LB)
    if include_kp:
        kp_entries: list[str] = []
        for variant, _ in columns:
            val = select_row(
                df,
                variant=variant,
                outcome=outcome,
                model=model,
                field="rkf",
            )
            kp_entries.append("--" if val.empty or pd.isna(val.iloc[0]) else f"{val.iloc[0]:,.2f}")
        lines.insert(-1, " & ".join(["KP rk Wald F", *kp_entries]) + LB)
    return lines


def fe_rows(columns: list[tuple[str, str]]) -> list[str]:
    ncol = len(columns)
    blank = " & ".join([""] * ncol)
    rows = [r"\textbf{Fixed Effects} & " + blank + LB]

    def mark(flag: bool) -> str:
        return r"$\checkmark$" if flag else ""

    for label, flag in FE_FLAGS:
        rows.append(" & ".join([INDENT + label, *([mark(flag)] * ncol)]) + LB)
    return rows


def build_table(
    *,
    df: pd.DataFrame,
    columns: list[tuple[str, str]],
    outcome: str,
) -> str:
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(columns))}}}",
    ]
    lines.extend(header_lines(columns))
    lines.append(r"\addlinespace[2pt]")

    panels = (("OLS", False, "Panel A: OLS"), ("IV", True, "Panel B: IV"))
    for idx, (model, include_kp, panel_label) in enumerate(panels):
        lines.append(
            rf"\multicolumn{{{len(columns)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")
        lines.extend(param_section(df, columns=columns, outcome=outcome, model=model))
        lines.append(MID)
        lines.extend(stat_section(df, columns=columns, outcome=outcome, model=model, include_kp=include_kp))
        if idx == 0:
            lines.append(MID)

    lines.append(MID)
    lines.extend(fe_rows(columns))
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-root",
        type=Path,
        default=RESULTS_RAW,
        help="Base directory containing the spec result folders.",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS.keys()),
        default="drop",
        help="Which CSA scenario to use (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination TeX file (defaults to results/cleaned/tex/user_productivity_<scenario>_top_metros.tex).",
    )
    parser.add_argument(
        "--outcome",
        default="total_contributions_q100",
        help="Outcome to display (default: total_contributions_q100).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    variant_entries = SCENARIOS[args.scenario]
    df, columns = combine_variants(results_root=args.results_root, entries=variant_entries)

    output_path = args.output
    if output_path is None:
        output_path = RESULTS_CLEANED_TEX / f"user_productivity_{args.scenario}_top_metros.tex"
    ensure_dir(output_path.parent)

    tex = build_table(df=df, columns=columns, outcome=args.outcome)
    output_path.write_text(tex)
    print(f"Wrote {args.scenario} top-CSA table → {output_path}")


if __name__ == "__main__":
    main()
