#!/usr/bin/env python3
"""Format the Python Crunchbase fundraising follow-ups into LaTeX tables.

These follow-ups correspond to the transcript meeting asks (excluding IPO logic):
  - age restrictions (Age<10, Age<20)
  - intensive margin (USD>0 only)
  - restrict to firms ever raising any round
  - geographic splits (NY/SF vs outside) + an interaction spec

Reads:
  results/raw/firm_scaling_crunchbase_fundraising_followups_python_pure/consolidated_results.csv
  results/raw/firm_scaling_crunchbase_fundraising_followups_python_pure/sample_sizes.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_followups_python_restrictions.tex
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_followups_python_geography.tex
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_followups_python_geography_ca_ny.tex
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
)


LB = r" \\"
INDENT = r"\hspace{1em}"

RAW_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_followups_python_pure"
RAW_RESULTS = RAW_DIR / "consolidated_results.csv"
RAW_SIZES = RAW_DIR / "sample_sizes.csv"

DEFAULT_OUT_RESTR = (
    RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_followups_python_restrictions.tex"
)
DEFAULT_OUT_GEO = (
    RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_followups_python_geography.tex"
)
DEFAULT_OUT_GEO_CA_NY = (
    RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_followups_python_geography_ca_ny.tex"
)


VAR3 = "var3"

VAR3_LABEL = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"
VAR3_OUT_NY_SF = "var3_outside"
VAR3_OUT_LABEL_NY_SF = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \mathds{1}(\text{Outside NY/SF}) $"

VAR3_OUT_CA_NY = "var3_outside_ca_ny"
VAR3_OUT_LABEL_CA_NY = r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \mathds{1}(\text{Outside CA/NY}) $"

OUTCOME = "cb_log1p_raised_usd"
SAMPLE = "matched_private"


def column_format_padded(n_numeric: int) -> str:
    return "l" + (r"@{\extracolsep{\fill}}c" * n_numeric)


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(rec: pd.Series | None) -> str:
    if rec is None:
        return "--"
    coef = rec.get("coef")
    se = rec.get("se")
    pval = rec.get("pval")
    if pd.isna(coef) or pd.isna(se) or pd.isna(pval) or float(se) == 0:
        return r"\makecell[c]{\textit{omitted}}"
    coef = float(coef)
    se = float(se)
    pval = float(pval)
    return rf"\makecell[c]{{{coef:.3f}{stars(pval)}\\({se:.3f})}}"


def fmt_int(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{int(x):,}"


def fmt_num(x: float | None, *, decimals: int = 3) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{float(x):.{decimals}f}"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not RAW_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing raw followups results: {RAW_RESULTS}. "
            "Run: python src/py/run_crunchbase_fundraising_followups_python_pure.py"
        )
    if not RAW_SIZES.exists():
        raise FileNotFoundError(
            f"Missing followups sample sizes: {RAW_SIZES}. "
            "Run: python src/py/run_crunchbase_fundraising_followups_python_pure.py"
        )
    res = pd.read_csv(RAW_RESULTS)
    sizes = pd.read_csv(RAW_SIZES)

    need_res = {"sample_tag", "spec_tag", "model_type", "outcome", "param", "coef", "se", "pval", "rkf", "pre_mean", "nobs"}
    miss_res = need_res - set(res.columns)
    if miss_res:
        raise RuntimeError(f"Missing columns {sorted(miss_res)} in {RAW_RESULTS}.")

    need_sizes = {"sample_tag", "spec_tag", "n_obs", "n_firms"}
    miss_sizes = need_sizes - set(sizes.columns)
    if miss_sizes:
        raise RuntimeError(f"Missing columns {sorted(miss_sizes)} in {RAW_SIZES}.")

    return res, sizes


def get_row(
    df: pd.DataFrame,
    *,
    spec: str,
    model: str,
    param: str,
    outcome: str = OUTCOME,
    sample: str = SAMPLE,
) -> pd.Series | None:
    sub = df[
        (df["sample_tag"] == sample)
        & (df["spec_tag"] == spec)
        & (df["model_type"] == model)
        & (df["outcome"] == outcome)
        & (df["param"] == param)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def get_sizes(sizes: pd.DataFrame, *, spec: str, sample: str = SAMPLE) -> tuple[int | None, int | None]:
    sub = sizes[(sizes["sample_tag"] == sample) & (sizes["spec_tag"] == spec)].head(1)
    if sub.empty:
        return None, None
    n_obs = sub.iloc[0].get("n_obs")
    n_firms = sub.iloc[0].get("n_firms")
    return (None if pd.isna(n_obs) else int(n_obs)), (None if pd.isna(n_firms) else int(n_firms))


def build_table(
    results: pd.DataFrame,
    sizes: pd.DataFrame,
    *,
    columns: list[tuple[str, str]],  # (spec_tag, latex label)
    include_outside_row: bool,
    outside_param: str = VAR3_OUT_NY_SF,
    outside_label: str = VAR3_OUT_LABEL_NY_SF,
) -> str:
    headers = [""] + [lbl for _, lbl in columns]
    ncols = len(columns)

    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(ncols)}}}",
        TOP,
        " & ".join(headers) + LB,
        MID,
    ]

    def _panel(title: str) -> None:
        lines.append(r"\addlinespace[2pt]")
        lines.append(rf"\multicolumn{{{ncols + 1}}}{{@{{}}l}}{{\textbf{{\uline{{{title}}}}}}} {LB}")
        lines.append(r"\addlinespace[2pt]")

    def _row(model: str, param: str, label: str) -> None:
        cells = [INDENT + label]
        for spec, _ in columns:
            rec = get_row(results, spec=spec, model=model, param=param)
            cells.append(coef_cell(rec))
        lines.append(" & ".join(cells) + LB)

    # Panel A: OLS
    _panel("Panel A: OLS")
    _row("OLS", VAR3, VAR3_LABEL)
    if include_outside_row:
        _row("OLS", outside_param, outside_label)

    lines.append(MID)

    # Panel B: IV
    _panel("Panel B: IV")
    _row("IV", VAR3, VAR3_LABEL)
    if include_outside_row:
        _row("IV", outside_param, outside_label)

    lines.append(MID)

    # Summary rows (one set for all columns)
    pre_cells = ["Pre-Covid Mean"]
    f_cells = ["KP rk Wald F"]
    nobs_cells = ["N (obs)"]
    nfirm_cells = ["N (firms)"]
    for spec, _ in columns:
        rec_any = get_row(results, spec=spec, model="OLS", param=VAR3)
        pre = None if rec_any is None else rec_any.get("pre_mean")
        pre_cells.append(fmt_num(None if pd.isna(pre) else float(pre), decimals=3))

        rec_iv = get_row(results, spec=spec, model="IV", param=VAR3)
        rkf = None if rec_iv is None else rec_iv.get("rkf")
        f_cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")

        n_obs, n_firms = get_sizes(sizes, spec=spec)
        nobs_cells.append(fmt_int(n_obs))
        nfirm_cells.append(fmt_int(n_firms))

    lines.append(" & ".join(pre_cells) + LB)
    lines.append(" & ".join(f_cells) + LB)
    lines.append(" & ".join(nobs_cells) + LB)
    lines.append(" & ".join(nfirm_cells) + LB)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-restrictions", type=Path, default=DEFAULT_OUT_RESTR)
    p.add_argument("--output-geography", type=Path, default=DEFAULT_OUT_GEO)
    p.add_argument("--output-geography-ca-ny", type=Path, default=DEFAULT_OUT_GEO_CA_NY)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    results, sizes = load_inputs()

    cols_restr = [
        ("baseline", "Baseline"),
        ("age_lt10", r"Age$<10$"),
        ("age_lt20", r"Age$<20$"),
        ("pos_usd_only", r"\makecell[c]{USD$>0$\\only}"),
        ("firms_ever_round", r"\makecell[c]{Ever\\round}"),
    ]
    tex_restr = build_table(results, sizes, columns=cols_restr, include_outside_row=False)
    ensure_dir(args.output_restrictions.parent)
    args.output_restrictions.write_text(tex_restr, encoding="utf-8")
    print(f"Wrote followups restrictions table → {args.output_restrictions}")

    cols_geo = [
        ("baseline", "Baseline"),
        ("hq_ny_sf", r"\makecell[c]{HQ\\NY/SF}"),
        ("hq_outside_ny_sf", r"\makecell[c]{HQ outside\\NY/SF}"),
        ("geo_interaction", r"\makecell[c]{Interaction\\(Outside)}"),
    ]
    tex_geo = build_table(results, sizes, columns=cols_geo, include_outside_row=True)
    ensure_dir(args.output_geography.parent)
    args.output_geography.write_text(tex_geo, encoding="utf-8")
    print(f"Wrote followups geography table → {args.output_geography}")

    cols_geo_ca_ny = [
        ("baseline", "Baseline"),
        ("hq_ca_ny", r"\makecell[c]{HQ\\CA/NY}"),
        ("hq_outside_ca_ny", r"\makecell[c]{HQ outside\\CA/NY}"),
        ("geo_interaction_ca_ny", r"\makecell[c]{Interaction\\(Outside)}"),
    ]
    tex_geo_ca_ny = build_table(
        results,
        sizes,
        columns=cols_geo_ca_ny,
        include_outside_row=True,
        outside_param=VAR3_OUT_CA_NY,
        outside_label=VAR3_OUT_LABEL_CA_NY,
    )
    ensure_dir(args.output_geography_ca_ny.parent)
    args.output_geography_ca_ny.write_text(tex_geo_ca_ny, encoding="utf-8")
    print(f"Wrote followups CA/NY geography table → {args.output_geography_ca_ny}")


if __name__ == "__main__":
    main()
