#!/usr/bin/env python3
"""Format log(total contributions) table for user productivity.

Outputs a two-column table (log total, log(1+total)) for the baseline sample
with Panel A (OLS) and Panel B (IV).
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

from build_baseline_table import (  # type: ignore
    PARAM_LABEL,
    PARAM_ORDER,
    PREAMBLE_FLEX,
    build_fe_rows,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
    column_format,
)

OUTCOMES = [
    ("log_total_contributions", "Log(total)"),
    ("log_total_contributions_plus1", "Log(1+total)"),
]
OUTPUT_TEX = RESULTS_CLEANED_TEX / "user_productivity_log_precovid.tex"


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(coef: float, se: float, p: float) -> str:
    return rf"\makecell[c]{{{coef:.2f}{stars(p)}\\({se:.2f})}}"


def fe_rows_filtered(column_tags: list[str]) -> list[str]:
    """Return FE rows, dropping any sub-row with no checkmarks."""
    lines = build_fe_rows(column_tags)
    header, *rest = lines
    rest = [row for row in rest if r"\checkmark" in row]
    return [header, *rest] if rest else []


def load_results() -> pd.DataFrame:
    path = RESULTS_RAW / "user_productivity_log_precovid" / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing results: {path}")
    return pd.read_csv(path)


def subset(df: pd.DataFrame, *, model: str, outcome: str, param: str | None = None) -> pd.Series:
    mask = (df["model_type"] == model) & (df["outcome"] == outcome)
    if param:
        mask &= df["param"] == param
    sub = df[mask]
    return sub.iloc[0] if not sub.empty else pd.Series(dtype=float)


def panel_rows(df: pd.DataFrame, *, model: str, include_kp: bool, include_pre_mean: bool) -> list[str]:
    lines: list[str] = []
    indent = r"\hspace{1em}"
    for param in PARAM_ORDER:
        row = [indent + PARAM_LABEL[param]]
        for outcome, _ in OUTCOMES:
            sub = subset(df, model=model, outcome=outcome, param=param)
            if sub.empty or pd.isna(sub.get("coef")):
                row.append("--")
            else:
                row.append(coef_cell(sub["coef"], sub["se"], sub["pval"]))
        lines.append(" & ".join(row) + r" \\")

    lines.append(MID)
    if include_pre_mean:
        row = ["Pre-Covid Mean"]
        for outcome, _ in OUTCOMES:
            sub = subset(df, model=model, outcome=outcome)
            val = sub.get("pre_mean") if not sub.empty else float("nan")
            row.append("--" if pd.isna(val) else f"{val:.2f}")
        lines.append(" & ".join(row) + r" \\")

    if include_kp:
        row = ["KP rk Wald F"]
        for outcome, _ in OUTCOMES:
            sub = subset(df, model=model, outcome=outcome)
            val = sub.get("rkf") if not sub.empty else float("nan")
            row.append("--" if pd.isna(val) else f"{val:.2f}")
        lines.append(" & ".join(row) + r" \\")

    row = ["N"]
    for outcome, _ in OUTCOMES:
        sub = subset(df, model=model, outcome=outcome)
        val = sub.get("nobs") if not sub.empty else float("nan")
        row.append("--" if pd.isna(val) else f"{int(val):,}")
    lines.append(" & ".join(row) + r" \\")

    return lines


def build_table(df: pd.DataFrame) -> str:
    col_fmt = column_format(len(OUTCOMES))
    column_tags = ["init"] * len(OUTCOMES)
    width = len(column_tags) + 1

    # Three-row header: overall outcome span, then outcome labels, then column numbers.
    top_header = r" & \multicolumn{2}{c}{Contribution Rank} \\" 
    sub_header = " & ".join([""] + [label for _, label in OUTCOMES]) + r" \\" 
    cmid_group = rf"\cmidrule(lr){{2-{len(OUTCOMES)+1}}}"
    cmid_sub = r"\cmidrule(lr){2-2}\cmidrule(lr){3-3}"
    header_nums = " & ".join([""] + [f"({i})" for i, _ in enumerate(OUTCOMES, start=1)]) + r" \\" 

    panel_a = panel_rows(df, model="OLS", include_kp=False, include_pre_mean=True)
    panel_b = panel_rows(df, model="IV", include_kp=True, include_pre_mean=False)
    fe_block = fe_rows_filtered(column_tags)

    lines = [
        rf"\begin{{tabular*}}{{\linewidth}}{{{col_fmt}}}",
        TOP,
        top_header,
        cmid_group,
        sub_header,
        cmid_sub,
        header_nums,
        MID,
        rf"\multicolumn{{{width}}}{{@{{}}l}}{{\textbf{{\uline{{Panel A: OLS}}}}}} \\",
        r"\addlinespace[2pt]",
        *panel_a,
        MID,
        rf"\multicolumn{{{width}}}{{@{{}}l}}{{\textbf{{\uline{{Panel B: IV}}}}}} \\",
        r"\addlinespace[2pt]",
        *panel_b,
        *( [MID, *fe_block] if fe_block else [] ),
        BOTTOM,
        r"\end{tabular*}",
    ]

    return PREAMBLE_FLEX + "\n".join(lines)


def main() -> None:
    df = load_results()
    tex = build_table(df)
    OUTPUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX.write_text(tex + "\n")
    print(f"Wrote log contributions table to {OUTPUT_TEX}")


if __name__ == "__main__":
    main()
