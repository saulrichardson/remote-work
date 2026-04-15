#!/usr/bin/env python3
"""Format the canonical Crunchbase fundraising results into LaTeX tables.

Consumes Stata exports produced by:
  spec/stata/firm_scaling_crunchbase_fundraising.do

Reads:
  results/raw/firm_scaling_crunchbase_fundraising/consolidated_results.csv
  results/raw/firm_scaling_crunchbase_fundraising/outcome_diagnostics.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_fundraising.tex
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_robustness.tex
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_additional.tex
"""

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
)

LB = r" \\"
INDENT = r"\hspace{1em}"


RAW_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising"
RAW_RESULTS = RAW_DIR / "consolidated_results.csv"
RAW_DIAGNOSTICS = RAW_DIR / "outcome_diagnostics.csv"


VAR3 = "var3"
VAR4 = "var4"
VAR3_LABEL = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"
VAR4_LABEL = r"$ \text{Startup} \times \mathds{1}(\text{Post}) $"


MAIN_SAMPLE = "private"

ROBUSTNESS_SAMPLES: Sequence[tuple[str, str]] = (
    ("private", "Baseline: Private (drop public)"),
    ("startup", "Robustness: Startup-only"),
    ("no_name_only", "Robustness: Drop name-only matches"),
)


COLUMNS: Sequence[tuple[str, str]] = (
    ("cb_any_round", r"\makecell[c]{Any\\round}"),
    ("cb_gt1_round", r"\makecell[c]{$>1$\\round}"),
    ("cb_gt2_round", r"\makecell[c]{$>2$\\round}"),
    ("cb_log1p_raised_usd", r"\makecell[c]{log(1+\\USD\\raised)}"),
    ("cb_raised_usd_q100", r"\makecell[c]{USD\\raised\\(q100)}"),
)

ADDITIONAL_COLUMNS: Sequence[tuple[str, str]] = (
    ("cb_round_count", r"\makecell[c]{\#\\rounds}"),
    ("cb_seriesAplus_round", r"\makecell[c]{Series\\A+\\round}"),
    ("cb_log_raised_usd", r"\makecell[c]{log(USD\\raised)\\($>0$)}"),
    ("cb_seriesAplus_cum", r"\makecell[c]{Ever\\Series\\A+}"),
    ("cb_log1p_cum_raised_usd", r"\makecell[c]{log(1+\\cum\\USD\\raised)}"),
)


def column_format_padded(n_numeric: int) -> str:
    # Use tabular* stretching but keep default outer padding (avoid edge clipping).
    # This is a local override of user_productivity.build_baseline_table.column_format,
    # which uses @{} ... @{} (flush to margins).
    return "l" + (r"@{\extracolsep{\fill}}c" * n_numeric)


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def require_columns(df: pd.DataFrame, path: Path, cols: set[str]) -> None:
    missing = cols - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {path}.")


def load_results() -> pd.DataFrame:
    if not RAW_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing raw results: {RAW_RESULTS}. "
            "Run: do spec/stata/firm_scaling_crunchbase_fundraising.do"
        )
    df = pd.read_csv(RAW_RESULTS)
    require_columns(
        df,
        RAW_RESULTS,
        {
            "sample_tag",
            "model_type",
            "outcome",
            "param",
            "coef",
            "se",
            "pval",
            "pre_mean",
            "rkf",
            "partialF",
            "nobs",
        },
    )
    return df


def load_diagnostics() -> pd.DataFrame:
    if not RAW_DIAGNOSTICS.exists():
        raise FileNotFoundError(
            f"Missing diagnostics: {RAW_DIAGNOSTICS}. "
            "Run: do spec/stata/firm_scaling_crunchbase_fundraising.do"
        )
    df = pd.read_csv(RAW_DIAGNOSTICS)
    require_columns(
        df,
        RAW_DIAGNOSTICS,
        {
            "sample_tag",
            "outcome",
            "n_total",
            "n_nonmiss",
            "n_missing",
            "share_zero",
            "mean_all",
            "mean_pre",
        },
    )
    return df


def select_row(
    df: pd.DataFrame,
    *,
    sample: str,
    outcome: str,
    model: str,
    param: str = VAR3,
) -> pd.Series | None:
    sub = df[
        (df["sample_tag"] == sample)
        & (df["outcome"] == outcome)
        & (df["model_type"] == model)
        & (df["param"] == param)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def diag_value(
    diag: pd.DataFrame,
    *,
    sample: str,
    outcome: str,
    field: str,
) -> float | None:
    sub = diag[(diag["sample_tag"] == sample) & (diag["outcome"] == outcome)].head(1)
    if sub.empty:
        return None
    val = sub.iloc[0].get(field)
    if pd.isna(val):
        return None
    return float(val)


def coef_cell(rec: pd.Series | None) -> str:
    if rec is None:
        return "--"
    coef = rec.get("coef")
    se = rec.get("se")
    pval = rec.get("pval")
    if pd.isna(coef) or pd.isna(se) or pd.isna(pval):
        return r"\makecell[c]{\textit{omitted}}"
    coef = float(coef)
    se = float(se)
    pval = float(pval)
    if se == 0:
        return r"\makecell[c]{\textit{omitted}}"
    return rf"\makecell[c]{{{coef:.3f}{stars(pval)}\\({se:.3f})}}"


def header_lines(columns: Sequence[tuple[str, str]]) -> list[str]:
    labels = " & ".join(label for _, label in columns)
    numbers = " & ".join(f"({i})" for i in range(1, len(columns) + 1))
    return [
        TOP,
        r" & " + labels + LB,
        r"\cmidrule(lr){2-" + f"{len(columns) + 1}" + r"}",
        " & " + numbers + LB,
        MID,
    ]


def fmt_share(x: float | None) -> str:
    if x is None:
        return ""
    return f"{x:.3f}"


def fmt_num(x: float | None, *, decimals: int = 3) -> str:
    if x is None:
        return ""
    return f"{x:.{decimals}f}"


def fmt_int(x: float | None) -> str:
    if x is None:
        return ""
    return f"{int(x):,}"


def build_main_table(results: pd.DataFrame, diag: pd.DataFrame) -> str:
    cols = COLUMNS
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(cols))}}}",
    ]
    lines.extend(header_lines(cols))
    lines.append(r"\addlinespace[2pt]")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(
            rf"\multicolumn{{{len(cols)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")

        # Parameter rows (reflect actual RHS used in the regression)
        for param, label in ((VAR3, VAR3_LABEL), (VAR4, VAR4_LABEL)):
            row_cells = [INDENT + label]
            for outcome, _ in cols:
                rec = select_row(
                    results,
                    sample=MAIN_SAMPLE,
                    outcome=outcome,
                    model=model,
                    param=param,
                )
                row_cells.append(coef_cell(rec))
            lines.append(" & ".join(row_cells) + LB)

        lines.append(MID)

        # Pre-covid mean + share zeros + N (from diagnostics)
        pre_cells = ["Pre-Covid Mean"]
        zero_cells = ["Share Zero"]
        n_cells = ["N"]
        for outcome, _ in cols:
            pre = diag_value(diag, sample=MAIN_SAMPLE, outcome=outcome, field="mean_pre")
            share0 = diag_value(diag, sample=MAIN_SAMPLE, outcome=outcome, field="share_zero")
            nobs = diag_value(diag, sample=MAIN_SAMPLE, outcome=outcome, field="n_nonmiss")
            pre_cells.append(fmt_num(pre, decimals=3))
            zero_cells.append(fmt_share(share0))
            n_cells.append(fmt_int(nobs))
        lines.append(" & ".join(pre_cells) + LB)
        lines.append(" & ".join(zero_cells) + LB)

        if model == "IV":
            f_cells = ["KP rk Wald F"]
            for outcome, _ in cols:
                rec = select_row(results, sample=MAIN_SAMPLE, outcome=outcome, model="IV")
                rkf = None if rec is None else rec.get("rkf")
                f_cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")
            lines.append(" & ".join(f_cells) + LB)

        lines.append(" & ".join(n_cells) + LB)

        if panel_label == "Panel A: OLS":
            lines.append(MID)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def build_robustness_table(results: pd.DataFrame, diag: pd.DataFrame) -> str:
    cols = COLUMNS
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(cols))}}}",
    ]
    lines.extend(header_lines(cols))
    lines.append(r"\addlinespace[2pt]")

    for sample_tag, sample_title in ROBUSTNESS_SAMPLES:
        lines.append(
            rf"\multicolumn{{{len(cols)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{sample_title}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")

        # IV only: show RHS terms used (var3 + var4).
        for param, label in ((VAR3, VAR3_LABEL), (VAR4, VAR4_LABEL)):
            row_cells = [INDENT + label]
            for outcome, _ in cols:
                rec = select_row(
                    results,
                    sample=sample_tag,
                    outcome=outcome,
                    model="IV",
                    param=param,
                )
                row_cells.append(coef_cell(rec))
            lines.append(" & ".join(row_cells) + LB)

        lines.append(MID)

        pre_cells = ["Pre-Covid Mean"]
        zero_cells = ["Share Zero"]
        f_cells = ["KP rk Wald F"]
        n_cells = ["N"]
        for outcome, _ in cols:
            pre = diag_value(diag, sample=sample_tag, outcome=outcome, field="mean_pre")
            share0 = diag_value(diag, sample=sample_tag, outcome=outcome, field="share_zero")
            nobs = diag_value(diag, sample=sample_tag, outcome=outcome, field="n_nonmiss")
            rec = select_row(results, sample=sample_tag, outcome=outcome, model="IV")
            rkf = None if rec is None else rec.get("rkf")

            pre_cells.append(fmt_num(pre, decimals=3))
            zero_cells.append(fmt_share(share0))
            f_cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")
            n_cells.append(fmt_int(nobs))

        lines.append(" & ".join(pre_cells) + LB)
        lines.append(" & ".join(zero_cells) + LB)
        lines.append(" & ".join(f_cells) + LB)
        lines.append(" & ".join(n_cells) + LB)

        if sample_tag != ROBUSTNESS_SAMPLES[-1][0]:
            lines.append(MID)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def build_additional_table(results: pd.DataFrame, diag: pd.DataFrame) -> str:
    cols = ADDITIONAL_COLUMNS
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(cols))}}}",
    ]
    lines.extend(header_lines(cols))
    lines.append(r"\addlinespace[2pt]")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(
            rf"\multicolumn{{{len(cols)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")

        for param, label in ((VAR3, VAR3_LABEL), (VAR4, VAR4_LABEL)):
            row_cells = [INDENT + label]
            for outcome, _ in cols:
                rec = select_row(
                    results,
                    sample=MAIN_SAMPLE,
                    outcome=outcome,
                    model=model,
                    param=param,
                )
                row_cells.append(coef_cell(rec))
            lines.append(" & ".join(row_cells) + LB)

        lines.append(MID)

        pre_cells = ["Pre-Covid Mean"]
        zero_cells = ["Share Zero"]
        n_cells = ["N"]
        for outcome, _ in cols:
            pre = diag_value(diag, sample=MAIN_SAMPLE, outcome=outcome, field="mean_pre")
            share0 = diag_value(diag, sample=MAIN_SAMPLE, outcome=outcome, field="share_zero")
            nobs = diag_value(diag, sample=MAIN_SAMPLE, outcome=outcome, field="n_nonmiss")
            pre_cells.append(fmt_num(pre, decimals=3))
            zero_cells.append(fmt_share(share0))
            n_cells.append(fmt_int(nobs))

        lines.append(" & ".join(pre_cells) + LB)
        lines.append(" & ".join(zero_cells) + LB)

        if model == "IV":
            f_cells = ["KP rk Wald F"]
            for outcome, _ in cols:
                rec = select_row(results, sample=MAIN_SAMPLE, outcome=outcome, model="IV")
                rkf = None if rec is None else rec.get("rkf")
                f_cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")
            lines.append(" & ".join(f_cells) + LB)

        lines.append(" & ".join(n_cells) + LB)

        if panel_label == "Panel A: OLS":
            lines.append(MID)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-main",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising.tex",
        help="Destination TeX file for main table.",
    )
    parser.add_argument(
        "--output-robustness",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_robustness.tex",
        help="Destination TeX file for robustness table.",
    )
    parser.add_argument(
        "--output-additional",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_additional.tex",
        help="Destination TeX file for additional outcomes table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = load_results()
    diag = load_diagnostics()

    ensure_dir(args.output_main.parent)
    args.output_main.write_text(build_main_table(results, diag), encoding="utf-8")
    print(f"Wrote main table → {args.output_main}")

    ensure_dir(args.output_robustness.parent)
    args.output_robustness.write_text(build_robustness_table(results, diag), encoding="utf-8")
    print(f"Wrote robustness table → {args.output_robustness}")

    ensure_dir(args.output_additional.parent)
    args.output_additional.write_text(build_additional_table(results, diag), encoding="utf-8")
    print(f"Wrote additional table → {args.output_additional}")


if __name__ == "__main__":
    main()
