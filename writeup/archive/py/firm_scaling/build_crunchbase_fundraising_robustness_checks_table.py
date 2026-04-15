#!/usr/bin/env python3
"""Format Crunchbase fundraising robustness checks into a compact LaTeX table.

Consumes Stata exports produced by:
  spec/stata/firm_scaling_crunchbase_fundraising_robustness.do

Reads:
  results/raw/firm_scaling_crunchbase_fundraising_robustness/consolidated_results.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_robustness_checks.tex
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

RAW_DIR = RESULTS_RAW / "firm_scaling_crunchbase_fundraising_robustness"
RAW_RESULTS = RAW_DIR / "consolidated_results.csv"

OUT_TEX = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_robustness_checks.tex"

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


def coef_cell(coef: float | None, se: float | None, pval: float | None) -> str:
    if coef is None or se is None or pval is None:
        return "--"
    if pd.isna(coef) or pd.isna(se) or pd.isna(pval) or float(se) == 0:
        return r"\makecell[c]{\textit{omitted}}"
    coef = float(coef)
    se = float(se)
    pval = float(pval)
    return rf"\makecell[c]{{{coef:.3f}{stars(pval)}\\({se:.3f})}}"


def get_row(
    df: pd.DataFrame,
    *,
    spec: str,
    outcome: str,
    param: str,
    model: str = "IV",
) -> pd.Series | None:
    sub = df[
        (df["spec_tag"] == spec)
        & (df["outcome"] == outcome)
        & (df["param"] == param)
        & (df["model_type"] == model)
    ].head(1)
    if sub.empty:
        return None
    return sub.iloc[0]


def fmt_int(x: float | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{int(x):,}"


def fmt_num(x: float | None, *, decimals: int = 2) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{float(x):.{decimals}f}"


def build_panel(
    df: pd.DataFrame,
    *,
    panel_title: str,
    rows: list[tuple[str, str]],  # (spec_tag, row_label)
    outcomes: list[tuple[str, str, str]],  # (outcome, col_label, param)
    model_type: str,
    include_f_and_n: bool = True,
) -> list[str]:
    lines: list[str] = []
    lines.append(r"\addlinespace[2pt]")
    lines.append(rf"\multicolumn{{{1 + len(outcomes) + (2 if include_f_and_n else 0)}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_title}}}}}}} {LB}")
    lines.append(r"\addlinespace[2pt]")

    for spec, label in rows:
        cells: list[str] = [label]
        fstats: list[float] = []
        nobss: list[float] = []
        for outcome, _, param in outcomes:
            rec = get_row(df, spec=spec, outcome=outcome, param=param, model=model_type)
            if rec is None:
                cells.append("--")
                continue
            cells.append(coef_cell(rec.get("coef"), rec.get("se"), rec.get("pval")))
            if param in ("var3", "var3_pl"):
                partial_f = rec.get("partialF")
                if partial_f is not None and not pd.isna(partial_f):
                    fstats.append(float(partial_f))
                nobs = rec.get("nobs")
                if nobs is not None and not pd.isna(nobs):
                    nobss.append(float(nobs))

        if include_f_and_n:
            # N (and first-stage strength, for IV) can differ slightly across columns
            # (e.g., trimming introduces a few missings). Report the smallest N/F.
            fstat_min = min(fstats) if fstats else None
            nobs_min = min(nobss) if nobss else None
            cells.append(fmt_num(fstat_min, decimals=2))
            cells.append(fmt_int(nobs_min))

        lines.append(" & ".join(cells) + LB)

    return lines


def main() -> None:
    if not RAW_RESULTS.exists():
        raise FileNotFoundError(
            f"Missing raw results: {RAW_RESULTS}. "
            "Run: do spec/stata/firm_scaling_crunchbase_fundraising_robustness.do"
        )
    df = pd.read_csv(RAW_RESULTS)
    required = {
        "spec_tag",
        "model_type",
        "outcome",
        "param",
        "coef",
        "se",
        "pval",
        "partialF",
        "nobs",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {RAW_RESULTS}.")

    ensure_dir(OUT_TEX.parent)

    # Table scaffold
    cols_main = [
        ("cb_any_raised", r"\makecell[c]{Any\\USD\\raised}", "var3"),
        ("cb_log1p_raised_usd", r"\makecell[c]{log(1+\\USD\\raised)}", "var3"),
        ("cb_raised_usd_q100", r"\makecell[c]{USD\\raised\\(q100)}", "var3"),
    ]

    header_labels = " & ".join(label for _, label, _ in cols_main)
    lines: list[str] = [
        PREAMBLE_FLEX,
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(cols_main) + 2)}}}",
        TOP,
        r" & " + header_labels + r" & \makecell[c]{KP rk\\Wald F} & N" + LB,
        r"\cmidrule(lr){2-" + f"{len(cols_main) + 1}" + r"}",
        MID,
    ]

    # Panels A/B: Controls robustness (main sample), shown for OLS and IV.
    lines.extend(
        build_panel(
            df,
            panel_title="Panel A: Main Sample (Private Firms) — Control Bundles (OLS)",
            rows=[
                ("baseline", "Baseline"),
                ("cohort_linear_postshift", "Cohort control: (Founded-2000)$\\times$Post"),
                ("prod_growth", "Add control: contemporaneous growth"),
                ("prod_growth_lag", "Add control: lagged growth"),
            ],
            outcomes=cols_main,
            model_type="OLS",
            include_f_and_n=True,
        )
    )
    lines.extend(
        build_panel(
            df,
            panel_title="Panel B: Main Sample (Private Firms) — Control Bundles (IV)",
            rows=[
                ("baseline", "Baseline"),
                ("cohort_linear_postshift", "Cohort control: (Founded-2000)$\\times$Post"),
                ("prod_growth", "Add control: contemporaneous growth"),
                ("prod_growth_lag", "Add control: lagged growth"),
            ],
            outcomes=cols_main,
            model_type="IV",
            include_f_and_n=True,
        )
    )

    # Panel B: Tail sensitivity (log1p only; baseline spec, different outcome transforms)
    cols_tail = [
        ("cb_log1p_raised_usd", r"\makecell[c]{Baseline}", "var3"),
        ("cb_log1p_raised_usd_w99", r"\makecell[c]{Winsor\\p99}", "var3"),
        ("cb_log1p_raised_usd_w995", r"\makecell[c]{Winsor\\p99.5}", "var3"),
        ("cb_log1p_raised_usd_trim99", r"\makecell[c]{Trim\\top\\1\\\%}", "var3"),
    ]
    # Tail panel uses its own header row (different columns); start a new tabular block.
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    lines.append("")
    lines.append(PREAMBLE_FLEX)
    lines.append(rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(cols_tail) + 2)}}}")
    lines.append(TOP)
    lines.append(r" & " + " & ".join(lbl for _, lbl, _ in cols_tail) + r" & \makecell[c]{KP rk\\Wald F} & N" + LB)
    lines.append(r"\cmidrule(lr){2-" + f"{len(cols_tail) + 1}" + r"}")
    lines.append(MID)
    lines.extend(
        build_panel(
            df,
            panel_title="Panel C: Top-Tail Sensitivity — log(1+USD raised) (OLS)",
            rows=[
                ("baseline", "Remote$\\times$Post effect (var3)"),
            ],
            outcomes=[(o, "", p) for o, _, p in cols_tail],
            model_type="OLS",
            include_f_and_n=True,
        )
    )
    lines.extend(
        build_panel(
            df,
            panel_title="Panel D: Top-Tail Sensitivity — log(1+USD raised) (IV)",
            rows=[
                ("baseline", "Remote$\\times$Post effect (var3)"),
            ],
            outcomes=[(o, "", p) for o, _, p in cols_tail],
            model_type="IV",
            include_f_and_n=True,
        )
    )

    # Panel C: Placebo in pre-Covid (fake Post cutoffs); use placebo param name
    cols_placebo = [
        ("cb_any_raised", r"\makecell[c]{Any\\USD\\raised}", "var3_pl"),
        ("cb_log1p_raised_usd", r"\makecell[c]{log(1+\\USD\\raised)}", "var3_pl"),
        ("cb_raised_usd_q100", r"\makecell[c]{USD\\raised\\(q100)}", "var3_pl"),
    ]

    # Close tail tabular and start placebo tabular (keeps formatting compact).
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    lines.append("")
    lines.append(PREAMBLE_FLEX)
    lines.append(rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(cols_placebo) + 2)}}}")
    lines.append(TOP)
    lines.append(r" & " + " & ".join(lbl for _, lbl, _ in cols_placebo) + r" & \makecell[c]{KP rk\\Wald F} & N" + LB)
    lines.append(r"\cmidrule(lr){2-" + f"{len(cols_placebo) + 1}" + r"}")
    lines.append(MID)
    lines.extend(
        build_panel(
            df,
            panel_title="Panel E: Placebo in Pre-Covid Only — Remote$\\times$FakePost (OLS)",
            rows=[
                ("placebo_2018h2", "Fake Post begins 2018H2"),
                ("placebo_2019h1", "Fake Post begins 2019H1"),
            ],
            outcomes=cols_placebo,
            model_type="OLS",
            include_f_and_n=True,
        )
    )
    lines.extend(
        build_panel(
            df,
            panel_title="Panel F: Placebo in Pre-Covid Only — Remote$\\times$FakePost (IV)",
            rows=[
                ("placebo_2018h2", "Fake Post begins 2018H2"),
                ("placebo_2019h1", "Fake Post begins 2019H1"),
            ],
            outcomes=cols_placebo,
            model_type="IV",
            include_f_and_n=True,
        )
    )

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")

    OUT_TEX.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote robustness checks table → {OUT_TEX}")


if __name__ == "__main__":
    main()
