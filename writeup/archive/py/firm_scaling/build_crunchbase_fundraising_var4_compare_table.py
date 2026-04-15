#!/usr/bin/env python3
"""Build a LaTeX table comparing Crunchbase fundraising specs with vs without var4.

This is a diagnostic writeup for the PI question:
  Should the canonical firm FE × time FE Crunchbase spec include Startup×Post (var4)
  as a control, or run the "Remote×Post only" version?

Inputs (Stata exports):
  - results/raw/firm_scaling_crunchbase_fundraising/consolidated_results.csv
  - results/raw/firm_scaling_crunchbase_fundraising/outcome_diagnostics.csv
  - results/raw/firm_scaling_crunchbase_fundraising_pure/consolidated_results.csv

Produces:
  - results/cleaned/tex/firm_scaling_crunchbase_fundraising_var4_compare.tex
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


RAW_CANON_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising"
RAW_PURE_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_pure"

RAW_CANON_RESULTS = RAW_CANON_DIR / "consolidated_results.csv"
RAW_PURE_RESULTS = RAW_PURE_DIR / "consolidated_results.csv"
RAW_DIAGNOSTICS = RAW_CANON_DIR / "outcome_diagnostics.csv"
PANEL_CSV = DATA_CLEAN / "firm_panel_with_cb_funding.csv"


MAIN_SAMPLE = "private"
PARAM = "var3"
PARAM_LABEL = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"


COLUMNS: Sequence[tuple[str, str]] = (
    ("cb_any_round", r"\makecell[c]{Any\\round}"),
    ("cb_gt1_round", r"\makecell[c]{$>1$\\round}"),
    ("cb_gt2_round", r"\makecell[c]{$>2$\\round}"),
    ("cb_log1p_raised_usd", r"\makecell[c]{log(1+\\USD\\raised)}"),
    ("cb_raised_usd_q100", r"\makecell[c]{USD\\raised\\(q100)}"),
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


def load_results(path: Path) -> pd.DataFrame:
    if not path.exists():
        stata_cmd = PROJECT_ROOT / "bin" / "stata"
        raise FileNotFoundError(
            f"Missing raw results: {path}. "
            "Run Stata first. For the pure variant:\n"
            f"  {stata_cmd} -b do spec/stata/firm_scaling_crunchbase_fundraising.do pure"
        )
    df = pd.read_csv(path)
    require_columns(
        df,
        path,
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
    outcome: str,
    model: str,
    sample: str = MAIN_SAMPLE,
    param: str = PARAM,
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
    outcome: str,
    field: str,
    sample: str = MAIN_SAMPLE,
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
    coef = float(rec["coef"])
    se = float(rec["se"])
    pval = float(rec["pval"])
    return rf"\makecell[c]{{{coef:.3f}{stars(pval)}\\({se:.3f})}}"


def fmt_num(x: float | None, *, decimals: int = 3) -> str:
    if x is None:
        return ""
    return f"{x:.{decimals}f}"


def fmt_share(x: float | None) -> str:
    if x is None:
        return ""
    return f"{x:.3f}"


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


def rkf_row(
    results: pd.DataFrame,
    *,
    label: str,
    model: str = "IV",
) -> str:
    cells = [label]
    for outcome, _ in COLUMNS:
        rec = select_row(results, outcome=outcome, model=model)
        rkf = None if rec is None else rec.get("rkf")
        cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")
    return " & ".join(cells) + LB


def share_zero_usd_private() -> float | None:
    """Share cb_raised_usd == 0 in the baseline fundraising sample.

    This is used to report a meaningful "Share Zero" for the q100 rank column,
    since q100 bins are 1..100 and therefore never literally equal 0.
    """

    if not PANEL_CSV.exists():
        return None

    df = pd.read_csv(PANEL_CSV, low_memory=False)
    df = df[(df["cb_matched"] == 1) & (df["public"] != 1)].copy()
    if "cb_raised_usd" not in df.columns:
        return None

    s = pd.to_numeric(df["cb_raised_usd"], errors="coerce").dropna()
    if s.shape[0] == 0:
        return None
    return float((s == 0).mean())


def build_table(
    canon: pd.DataFrame,
    pure: pd.DataFrame,
    diag: pd.DataFrame,
    *,
    share_zero_usd: float | None,
) -> str:
    cols = COLUMNS

    row_label_canon = (
        INDENT
        + r"\makecell[l]{"
        + PARAM_LABEL
        + r"\\(controls: Startup$\times$Post)}"
    )
    row_label_pure = (
        INDENT
        + r"\makecell[l]{"
        + PARAM_LABEL
        + r"\\(no Startup$\times$Post control)}"
    )

    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format(len(cols))}}}",
    ]
    lines.extend(header_lines(cols))
    lines.append(r"\addlinespace[2pt]")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(
            rf"\multicolumn{{{len(cols)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")

        # Canonical row (with var4)
        row_cells = [row_label_canon]
        for outcome, _ in cols:
            rec = select_row(canon, outcome=outcome, model=model)
            row_cells.append(coef_cell(rec))
        lines.append(" & ".join(row_cells) + LB)

        # Pure row (no var4)
        row_cells = [row_label_pure]
        for outcome, _ in cols:
            rec = select_row(pure, outcome=outcome, model=model)
            row_cells.append(coef_cell(rec))
        lines.append(" & ".join(row_cells) + LB)

        lines.append(MID)

        if panel_label == "Panel A: OLS":
            lines.append(r"\addlinespace[2pt]")

    # Shared diagnostics for this sample (identical across specs because sample/outcomes identical)
    pre_cells = ["Pre-Covid Mean"]
    zero_cells = ["Share Zero"]
    n_cells = ["N"]
    for outcome, _ in cols:
        pre = diag_value(diag, outcome=outcome, field="mean_pre")
        if outcome == "cb_raised_usd_q100" and share_zero_usd is not None:
            share0 = share_zero_usd
        else:
            share0 = diag_value(diag, outcome=outcome, field="share_zero")
        nobs = diag_value(diag, outcome=outcome, field="n_nonmiss")
        pre_cells.append(fmt_num(pre, decimals=3))
        zero_cells.append(fmt_share(share0))
        n_cells.append(fmt_int(nobs))

    lines.append(" & ".join(pre_cells) + LB)
    lines.append(" & ".join(zero_cells) + LB)
    lines.append(rkf_row(canon, label="KP rk Wald F (with var4)"))
    lines.append(rkf_row(pure, label="KP rk Wald F (pure)"))
    lines.append(" & ".join(n_cells) + LB)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_var4_compare.tex",
        help="Destination TeX file for the var4 comparison table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    canon = load_results(RAW_CANON_RESULTS)
    pure = load_results(RAW_PURE_RESULTS)
    diag = load_diagnostics()
    share0_usd = share_zero_usd_private()

    ensure_dir(args.output.parent)
    args.output.write_text(build_table(canon, pure, diag, share_zero_usd=share0_usd), encoding="utf-8")
    print(f"Wrote table → {args.output}")


if __name__ == "__main__":
    main()
