#!/usr/bin/env python3
"""Build LaTeX tables comparing baseline vs cohort×year FE Crunchbase fundraising specs.

Meeting motivation (ask #2):
  - Remove startup×post (var4) entirely.
  - Control instead for founding-year cohort × calendar-year fixed effects.

This script consumes the exploratory Stata export that includes multiple FE variants:
  spec/stata/firm_scaling_crunchbase_fundraising_cohort_fe.do

Inputs:
  - results/raw/firm_scaling_crunchbase_fundraising_cohort_fe/consolidated_results.csv
  - data/clean/firm_panel_with_cb_funding.csv (for share-zero diagnostics)

Outputs:
  - results/cleaned/tex/firm_scaling_crunchbase_fundraising_cohort_fe_compare.tex
  - results/cleaned/tex/firm_scaling_crunchbase_fundraising_cohort_fe_compare_additional.tex
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

from project_paths import DATA_CLEAN, RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
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

RAW_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_cohort_fe"
RAW_RESULTS = RAW_DIR / "consolidated_results.csv"

PANEL_CSV = DATA_CLEAN / "firm_panel_with_cb_funding.csv"

# Spec tags are defined in the Stata runner.
SPEC_BASELINE = "pure_yh_fe"
SPEC_COHORT5_YEAR = "cohort5Xyear_fe"

PARAM = "var3"
PARAM_LABEL = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"

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


def stars(p: float) -> str:
    if pd.isna(p):
        return ""
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
            "Run: do spec/stata/firm_scaling_crunchbase_fundraising_cohort_fe.do"
        )
    df = pd.read_csv(RAW_RESULTS)
    require_columns(
        df,
        RAW_RESULTS,
        {
            "spec_tag",
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


def load_panel_private() -> pd.DataFrame:
    if not PANEL_CSV.exists():
        raise FileNotFoundError(
            f"Missing panel input: {PANEL_CSV}. "
            "Build via: python src/py/build_firm_scaling_crunchbase_outcomes.py"
        )
    df = pd.read_csv(PANEL_CSV, low_memory=False)
    # Sample policy matches the cohort FE runner: keep matched, drop public.
    df = df[(df["cb_matched"] == 1) & (df["public"] != 1)].copy()

    # Ensure numeric types for the columns we use in diagnostics.
    for col in [
        "covid",
        "cb_round_count",
        "cb_any_round",
        "cb_gt1_round",
        "cb_gt2_round",
        "cb_raised_usd",
        "cb_log1p_raised_usd",
        "cb_log1p_cum_raised_usd",
        "cb_seriesAplus_round",
        "cb_seriesAplus_cum",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Derived outcomes used in the tables but not stored on disk by the CB builder.
    if "cb_round_count" in df.columns:
        if "cb_any_round" not in df.columns:
            df["cb_any_round"] = (df["cb_round_count"] > 0).astype(float)
        df["cb_gt1_round"] = (df["cb_round_count"] > 1).astype(float)
        df["cb_gt2_round"] = (df["cb_round_count"] > 2).astype(float)

    return df


def select_row(
    df: pd.DataFrame,
    *,
    spec: str,
    outcome: str,
    model: str,
    param: str = PARAM,
) -> pd.Series | None:
    sub = df[
        (df["spec_tag"] == spec)
        & (df["outcome"] == outcome)
        & (df["model_type"] == model)
        & (df["param"] == param)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


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


def share_zero_by_outcome(panel: pd.DataFrame, outcomes: Sequence[str]) -> dict[str, float]:
    """Compute share of zeros for each outcome in the *analysis sample*.

    Notes:
      - For q100 (a derived within-half-year rank), we proxy zero-mass by reporting
        the share of observations with cb_raised_usd == 0.
      - For log(USD raised) on positives only, we also report the zero-mass in raw
        dollars (share cb_raised_usd == 0) since the log variable is missing at 0.
    """

    zero_source = {
        "cb_raised_usd_q100": "cb_raised_usd",
        "cb_log_raised_usd": "cb_raised_usd",
    }

    out: dict[str, float] = {}
    for outcome in outcomes:
        src = zero_source.get(outcome, outcome)
        if src not in panel.columns:
            continue
        s = panel[src]
        mask = s.notna()
        if mask.sum() == 0:
            continue
        out[outcome] = float((s[mask] == 0).mean())
    return out


def build_compare_table(results: pd.DataFrame, panel: pd.DataFrame, columns: Sequence[tuple[str, str]]) -> str:
    colnames = [c for c, _ in columns]
    share0 = share_zero_by_outcome(panel, colnames)

    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(columns))}}}",
    ]
    lines.extend(header_lines(columns))
    lines.append(r"\addlinespace[2pt]")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(
            rf"\multicolumn{{{len(columns)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")

        for spec, label in (
            (SPEC_BASELINE, rf"{INDENT}{PARAM_LABEL} (Half-year FE)"),
            (
                SPEC_COHORT5_YEAR,
                rf"{INDENT}{PARAM_LABEL} (Cohort(5y)$\times$Year FE)",
            ),
        ):
            row_cells = [label]
            for outcome, _ in columns:
                rec = select_row(results, spec=spec, outcome=outcome, model=model)
                row_cells.append(coef_cell(rec))
            lines.append(" & ".join(row_cells) + LB)

        lines.append(MID)

        # Pre-Covid mean (from baseline spec row; identical across specs by construction).
        pre_cells = ["Pre-Covid Mean"]
        for outcome, _ in columns:
            rec = select_row(results, spec=SPEC_BASELINE, outcome=outcome, model=model)
            pre = None if rec is None else rec.get("pre_mean")
            pre_cells.append("" if pre is None or pd.isna(pre) else fmt_num(float(pre), decimals=3))
        lines.append(" & ".join(pre_cells) + LB)

        # Share zero (analysis sample proxy; see share_zero_by_outcome).
        zero_cells = ["Share Zero"]
        for outcome, _ in columns:
            zero_cells.append(fmt_share(share0.get(outcome)))
        lines.append(" & ".join(zero_cells) + LB)

        if model == "IV":
            for spec, label in (
                (SPEC_BASELINE, "KP rk Wald F (Baseline)"),
                (SPEC_COHORT5_YEAR, "KP rk Wald F (Cohort5×Year)"),
            ):
                f_cells = [label]
                for outcome, _ in columns:
                    rec = select_row(results, spec=spec, outcome=outcome, model="IV")
                    rkf = None if rec is None else rec.get("rkf")
                    f_cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")
                lines.append(" & ".join(f_cells) + LB)

        for spec, label in (
            (SPEC_BASELINE, "N (Baseline)"),
            (SPEC_COHORT5_YEAR, "N (Cohort5×Year)"),
        ):
            n_cells = [label]
            for outcome, _ in columns:
                rec = select_row(results, spec=spec, outcome=outcome, model=model)
                nobs = None if rec is None else rec.get("nobs")
                n_cells.append("" if nobs is None or pd.isna(nobs) else fmt_int(float(nobs)))
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
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_cohort_fe_compare.tex",
        help="Destination TeX file for main compare table.",
    )
    parser.add_argument(
        "--output-additional",
        type=Path,
        default=RESULTS_CLEANED_TEX
        / "firm_scaling_crunchbase_fundraising_cohort_fe_compare_additional.tex",
        help="Destination TeX file for additional outcomes compare table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = load_results()
    panel = load_panel_private()

    ensure_dir(args.output_main.parent)
    args.output_main.write_text(build_compare_table(results, panel, COLUMNS), encoding="utf-8")
    print(f"Wrote main compare table → {args.output_main}")

    ensure_dir(args.output_additional.parent)
    args.output_additional.write_text(
        build_compare_table(results, panel, ADDITIONAL_COLUMNS), encoding="utf-8"
    )
    print(f"Wrote additional compare table → {args.output_additional}")


if __name__ == "__main__":
    main()
