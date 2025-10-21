#!/usr/bin/env python3
"""Create LaTeX tables for firm scaling location-concentration outcomes."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
RAW_DIR = PROJECT_ROOT / "results" / "raw"
CLEAN_DIR = PROJECT_ROOT / "results" / "cleaned"

SPEC_LOC = "firm_scaling_location_hhi"

PARAM_ORDER: list[str] = ["var3", "var5", "var4"]
PARAM_LABEL: dict[str, str] = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

def stack(*lines: str) -> str:
    body = ' \\'.join(lines)
    return rf"\begin{{tabular}}[c]{{@{{}}c@{{}}}}{body}\end{{tabular}}"


OUTCOME_ORDER: list[str] = ["hhi"]
OUTCOME_LABEL: dict[str, str] = {
    "hhi": stack("HHI", "(0-1)")
}

COL_TAG = "loc"
COL_CONFIG = [(outcome, COL_TAG) for outcome in OUTCOME_ORDER]

FIRM_FE_INCLUDED = {COL_TAG: True}
TIME_FE_INCLUDED = {COL_TAG: True}

STAR_RULES: list[tuple[float, str]] = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""



def indicator_row(label: str, mapping: dict[str, bool], col_tags: Iterable[str]) -> str:
    marks = [r"$\checkmark$" if mapping.get(tag, False) else "" for tag in col_tags]
    return " & ".join([label, *marks]) + " \\"


def stat_row(df: pd.DataFrame, *, label: str, field: str, fmt: str | None, model: str) -> str:
    vals: list[str] = []
    for outcome, tag in COL_CONFIG:
        mask = (
            (df["model_type"] == model)
            & (df["outcome"] == outcome)
            & (df["fe_tag"] == tag)
        )
        sub = df.loc[mask]
        if sub.empty or pd.isna(sub.iloc[0].get(field, None)):
            vals.append("")
        else:
            val = sub.iloc[0][field]
            vals.append(fmt.format(val) if fmt else str(val))
    return " & ".join([label, *vals]) + " \\"


def build_table(df: pd.DataFrame, *, model: str) -> str:
    include_kp = model == "IV"

    header_nums = " & ".join(["", *[f"({i})" for i, _ in enumerate(COL_CONFIG, start=1)]]) + r" \\"
    header_outcomes = " & ".join(["", *[OUTCOME_LABEL[o] for o, _ in COL_CONFIG]]) + r" \\"

    col_tags = [tag for _, tag in COL_CONFIG]

    coef_rows: list[str] = []
    for param in PARAM_ORDER:
        cells = [PARAM_LABEL[param]]
        for outcome, tag in COL_CONFIG:
            mask = (
                (df["model_type"] == model)
                & (df["outcome"] == outcome)
                & (df["fe_tag"] == tag)
                & (df["param"] == param)
            )
            if mask.any():
                row = df.loc[mask].iloc[0]
                coef, se, pval = row["coef"], row["se"], row["pval"]
                cell = stack(f"{coef:.3f}{stars(pval)}", f"({se:.3f})")
                cells.append(cell)
            else:
                cells.append("")
        coef_rows.append(" & ".join(cells) + " \\")
    coef_block = "\n".join(coef_rows)

    indicators = "\n".join(
        [
            indicator_row("Time FE", TIME_FE_INCLUDED, col_tags),
            indicator_row("Firm FE", FIRM_FE_INCLUDED, col_tags),
        ]
    )

    summary_rows = [
        stat_row(df, label="Pre-Covid Mean", field="pre_mean", fmt="{:.3f}", model=model)
    ]
    if include_kp:
        summary_rows.append(stat_row(df, label="KP rk Wald F", field="rkf", fmt="{:.2f}", model=model))
    summary_rows.append(stat_row(df, label="N", field="nobs", fmt="{:,}", model=model))
    summary_block = "\n".join(summary_rows)

    col_fmt = "l" + "c" * len(COL_CONFIG)

    lines = [
        rf"\begin{{tabular}}{{{col_fmt}}}",
        r"\toprule",
        header_nums,
        header_outcomes,
        r"\midrule",
        coef_block,
        r"\midrule",
        indicators,
        r"\midrule",
        summary_block,
        r"\bottomrule",
        r"\end{tabular}",
    ]

    return "\n".join(lines)


def load_data() -> pd.DataFrame:
    loc_path = RAW_DIR / SPEC_LOC / "consolidated_results.csv"
    if not loc_path.exists():
        raise FileNotFoundError(loc_path)
    df = pd.read_csv(loc_path)
    df["fe_tag"] = COL_TAG
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Format firm scaling location HHI tables")
    parser.add_argument("--model-type", choices=["ols", "iv"], default="ols")
    args = parser.parse_args()

    model = "IV" if args.model_type.lower() == "iv" else "OLS"

    df = load_data()
    table_body = build_table(df, model=model)

    caption = f"Firm Scaling — Location Concentration (HHI) — {model}"
    label = f"tab:firm_scaling_location_hhi_{args.model_type.lower()}"
    output_name = f"firm_scaling_location_hhi_{args.model_type.lower()}.tex"
    output_path = CLEAN_DIR / output_name

    tex_lines = [
        r"\begin{table}[H]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"{\scriptsize\centering",
        r"",
        table_body,
        r"}",
        r"\end{table}",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(tex_lines) + "\n")
    print(f"Wrote LaTeX table to {output_path}")


if __name__ == "__main__":
    main()
