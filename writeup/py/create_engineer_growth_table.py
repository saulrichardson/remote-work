#!/usr/bin/env python3
"""Build styled LaTeX table for engineer headcount growth results."""

from __future__ import annotations

from pathlib import Path
import pandas as pd
from textwrap import dedent


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

RAW_DIR = PROJECT_ROOT / "results" / "raw" / "firm_hiring_engineer_nonengineer"
CLEAN_DIR = PROJECT_ROOT / "results" / "cleaned"

OUTPUT_PATH = CLEAN_DIR / "engineer_hiring_remote.tex"

PARAMS = [
    ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
    ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
    ("var4", r"$ \text{Post} \times \text{Startup} $")
]

COLUMNS = ["OLS", "IV"]

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(pval: float) -> str:
    for cut, sym in STAR_RULES:
        if pval is not None and pval < cut:
            return sym
    return ""


def make_cell(coef: float, se: float, pval: float) -> str:
    return rf"\makecell[c]{{{coef:.4f}{stars(pval)}\\({se:.4f})}}"


def latex_row(cells: list[str]) -> str:
    return f"{' & '.join(cells)} \\\\"


def first_stage_min(fs: pd.DataFrame) -> float | None:
    if fs.empty:
        return None
    grouped = fs.groupby("endovar")["partialF"].max()
    if grouped.empty:
        return None
    return float(grouped.min())


def build_table(df: pd.DataFrame, fs: pd.DataFrame) -> str:
    header = latex_row(["", *COLUMNS])
    sub_header = latex_row(["", *["Engineer headcount growth (wins. 5–95)" for _ in COLUMNS]])

    body_rows: list[str] = []
    for param, label in PARAMS:
        cells = [label]
        for model in COLUMNS:
            match = df[(df["model_type"] == model) & (df["param"] == param)]
            if match.empty:
                cells.append("")
            else:
                coef, se, pval = match.iloc[0][["coef", "se", "pval"]]
                cells.append(make_cell(coef, se, pval))
        body_rows.append(latex_row(cells))

    fe_row = latex_row(["Firm FE", *[r"$\checkmark$" for _ in COLUMNS]])
    time_row = latex_row(["Half-year FE", *[r"$\checkmark$" for _ in COLUMNS]])

    def stat_row(label: str, field: str, fmt: str) -> str:
        entries: list[str] = [label]
        for model in COLUMNS:
            match = df[df["model_type"] == model]
            if match.empty or pd.isna(match.iloc[0][field]):
                entries.append("")
            else:
                entries.append(fmt.format(match.iloc[0][field]))
        return latex_row(entries)

    pre_mean_row = stat_row("Pre-Covid Mean", "pre_mean", "{:.4f}")
    n_row = stat_row("N", "nobs", "{:,}")

    # KP rk Wald F row: only IV column should show the value
    kp_entries = ["KP rk Wald $F$"]
    for model in COLUMNS:
        if model == "IV":
            match = df[df["model_type"] == model]
            rkf = match.iloc[0]["rkf"] if not match.empty else None
            kp_entries.append(f"{rkf:.2f}" if pd.notna(rkf) else "")
        else:
            kp_entries.append("")
    kp_row = latex_row(kp_entries)

    fs_min = first_stage_min(fs)
    fs_entries = ["First-stage $F$ (min)"]
    for model in COLUMNS:
        if model == "IV" and fs_min is not None:
            fs_entries.append(f"{fs_min:.2f}")
        else:
            fs_entries.append("")
    fs_row = latex_row(fs_entries)

    col_spec = "l" + "".join(["@{\\hspace{6pt}}c" for _ in COLUMNS]) + "@{\\hspace{0pt}}"
    body_block = "\n".join(body_rows)

    tabular = dedent(
        rf"""
        \begin{{tabularx}}{{\linewidth}}{{{col_spec}}}
        \toprule
        {header}
        \midrule
        {sub_header}
        \midrule
        {body_block}
        \midrule
        {fe_row}
        {time_row}
        \midrule
        {pre_mean_row}
        {fs_row}
        {kp_row}
        {n_row}
        \bottomrule
        \end{{tabularx}}
        """
    ).strip()

    wrapped = dedent(
        rf"""
        \begin{{table}}[H]
          \centering
          \caption{{Remote Adoption Raises Engineer Growth}}
          \label{{tab:engineer_hiring_remote}}
          {{\scriptsize\centering
          \centering
          {tabular}
          }}
        \end{{table}}
        """
    ).strip()

    return wrapped + "\n"


def main() -> None:
    results = pd.read_csv(RAW_DIR / "consolidated_results.csv")
    results = results[results["outcome"] == "Engineer growth rate"].copy()

    first_stage = pd.read_csv(RAW_DIR / "first_stage.csv")

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_table(results, first_stage))
    print(f"Wrote LaTeX table to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
