#!/usr/bin/env python3
"""Compact CSA table (keep/drop × firm×user FE only)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.py.project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore

PREAMBLE_FLEX = "\\centering\n"
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
}
LB = r" \\"
INDENT = r"\hspace{1em}"
PARAM_ORDER: tuple[str, ...] = ("var3", "var5")

COLUMN_ORDER: list[tuple[str, str]] = [
    ("precovid_keeptop5", "Keep CSAs Ranked 1–5"),
    ("precovid_keeptop10", "Keep CSAs Ranked 1–10"),
    ("precovid_droptop5", "Drop CSAs Ranked 1–5"),
    ("precovid_droptop10", "Drop CSAs Ranked 1–10"),
]

FE_FLAGS = {
    "firm": {
        "Time": True,
        "Firm": False,
        "Individual": False,
        "Firm $\\times$ Individual": True,
    },
}


def column_format(n_numeric: int) -> str:
    return r"@{}l" + (r"@{\extracolsep{\fill}}c" * n_numeric) + r"@{}"


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def build_columns() -> list[tuple[tuple[str, str], str]]:
    return [((variant, "firm"), label) for variant, label in COLUMN_ORDER]


def select(
    df: pd.DataFrame,
    *,
    variant: str,
    fe_kind: str,
    outcome: str,
    model: str,
    param: str | None = None,
    field: str | None = None,
) -> pd.Series:
    mask = (
        (df["variant"] == variant)
        & (df["fe_kind"] == fe_kind)
        & (df["outcome"] == outcome)
        & (df["model_type"] == model)
    )
    if param:
        mask &= df["param"] == param
    subset = df.loc[mask]
    if subset.empty:
        return pd.Series(dtype=float)
    if field:
        return pd.Series(subset.iloc[0][field])
    return subset.iloc[0]


def header_lines(columns: list[tuple[tuple[str, str], str]], label_map: dict[str, str]) -> list[str]:
    total_cols = len(columns)
    numbering = " & ".join(f"({i})" for i in range(1, total_cols + 1))

    groups = []
    idx = 0
    while idx < total_cols:
        (variant, _), _ = columns[idx]
        span = 1
        while idx + span < total_cols and columns[idx + span][0][0] == variant:
            span += 1
        label = label_map[variant]
        groups.append((label, span))
        idx += span

    group_cells = []
    for label, span in groups:
        words = label.split()
        if len(words) <= 1:
            display = label
        else:
            split_idx = len(words) // 2
            display = " ".join(words[:split_idx]) + r"\\ " + " ".join(words[split_idx:])
        group_cells.append(rf"\multicolumn{{{span}}}{{c}}{{\makecell[c]{{{display}}}}}")
    group_line = " & " + " & ".join(group_cells) + LB
    cmidrules = []
    col_start = 2
    for _, span in groups:
        col_end = col_start + span - 1
        cmidrules.append(rf"\cmidrule(lr){{{col_start}-{col_end}}}")
        col_start = col_end + 1

    return [
        TOP,
        group_line,
        " ".join(cmidrules),
        " & " + numbering + LB,
        MID,
    ]


def param_rows(
    df: pd.DataFrame,
    *,
    columns: list[tuple[tuple[str, str], str]],
    outcome: str,
    model: str,
) -> list[str]:
    rows: list[str] = []
    for param in PARAM_ORDER:
        cells = []
        for (variant, fe_kind), _ in columns:
            rec = select(
                df,
                variant=variant,
                fe_kind=fe_kind,
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


def stat_rows(
    df: pd.DataFrame,
    *,
    columns: list[tuple[tuple[str, str], str]],
    outcome: str,
    model: str,
    include_kp: bool,
) -> list[str]:
    def format_value(val: pd.Series, numeric: bool) -> str:
        if val.empty or pd.isna(val.iloc[0]):
            return "--"
        return f"{int(round(val.iloc[0])):,}" if numeric else f"{val.iloc[0]:,.2f}"

    lines: list[str] = []
    for field, label, numeric in (
        ("pre_mean", "Pre-Covid Mean", False),
        ("nobs", "N", True),
    ):
        entries = [
            format_value(
                select(
                    df,
                    variant=variant,
                    fe_kind=fe_kind,
                    outcome=outcome,
                    model=model,
                    field=field,
                ),
                numeric,
            )
            for (variant, fe_kind), _ in columns
        ]
        lines.append(" & ".join([label, *entries]) + LB)

    if include_kp:
        kp_entries = [
            format_value(
                select(
                    df,
                    variant=variant,
                    fe_kind=fe_kind,
                    outcome=outcome,
                    model=model,
                    field="rkf",
                ),
                False,
            )
            for (variant, fe_kind), _ in columns
        ]
        lines.insert(-1, " & ".join(["KP rk Wald F", *kp_entries]) + LB)
    return lines


def fe_block(columns: list[tuple[tuple[str, str], str]]) -> list[str]:
    lines = [r"\textbf{Fixed Effects} & " + " & ".join([""] * len(columns)) + LB]
    for label in ("Time", "Firm", "Individual", "Firm $\\times$ Individual"):
        entries = []
        for (_variant, fe_kind), _ in columns:
            entries.append(r"$\checkmark$" if FE_FLAGS[fe_kind].get(label, False) else "")
        lines.append(" & ".join([INDENT + label, *entries]) + LB)
    return lines


def build_table(
    df: pd.DataFrame,
    *,
    columns: list[tuple[tuple[str, str], str]],
    outcome: str,
    label_map: dict[str, str],
) -> str:
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(columns))}}}",
    ]
    lines.extend(header_lines(columns, label_map))
    lines.append(r"\addlinespace[2pt]")

    panels = (("OLS", False, "Panel A: OLS"), ("IV", True, "Panel B: IV"))
    for idx, (model, include_kp, panel_label) in enumerate(panels):
        lines.append(
            rf"\multicolumn{{{len(columns)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")
        lines.extend(param_rows(df, columns=columns, outcome=outcome, model=model))
        lines.append(MID)
        lines.extend(stat_rows(df, columns=columns, outcome=outcome, model=model, include_kp=include_kp))
        if idx == 0:
            lines.append(MID)

    lines.append(MID)
    lines.extend(fe_block(columns))
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
        "--output",
        type=Path,
        help="Destination TeX file (defaults to results/cleaned/tex/user_productivity_top_metros_firmbyuser.tex).",
    )
    parser.add_argument(
        "--outcome",
        default="total_contributions_q100",
        help="Outcome to display (default: total_contributions_q100).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frames = []
    asset_root = args.results_root / "08_user_productivity_top_metros_firmbyuser"
    for variant, _ in COLUMN_ORDER:
        csv = asset_root / variant / "consolidated_results.csv"
        if not csv.exists():
            raise FileNotFoundError(csv)
        frame = pd.read_csv(csv)
        frame["variant"] = variant
        frame["fe_kind"] = "firm"
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    columns = build_columns()
    label_map = dict(COLUMN_ORDER)

    output_path = args.output
    if output_path is None:
        output_path = RESULTS_CLEANED_TEX / "user_productivity_top_metros_firmbyuser.tex"
    ensure_dir(output_path.parent)

    tex = build_table(df, columns=columns, outcome=args.outcome, label_map=label_map)
    cleaned_lines = []
    skip_prefixes = (
        r"\hspace{1em}Firm &",
        r"\hspace{1em}Individual &",
    )
    for line in tex.splitlines():
        stripped = line.lstrip()
        if any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        cleaned_lines.append(line)
    tex = "\n".join(cleaned_lines)
    output_path.write_text(tex)
    print(f"Wrote firm×user CSA table → {output_path}")


if __name__ == "__main__":
    main()
