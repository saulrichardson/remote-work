 #!/usr/bin/env python3
"""Build a single LaTeX table for the "core 4" Crunchbase fundraising outcomes.

Consumes Stata exports produced by:
  spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do

Reads:
  results/raw/03_firm_scaling_crunchbase_fundraising_core4/consolidated_results.csv
  results/raw/03_firm_scaling_crunchbase_fundraising_core4/outcome_diagnostics.csv

Writes:
  results/cleaned/tex/firm_scaling_crunchbase_fundraising_core4.tex
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import pandas as pd

from src.py.project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir, require_file  # type: ignore

PREAMBLE_FLEX = "\\centering\n"
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]
TOP = r"\toprule"
MID = r"\midrule"
BOTTOM = r"\bottomrule"

LB: Final[str] = r" \\"
INDENT: Final[str] = r"\hspace{1em}"

RAW_DIR = RESULTS_RAW / "03_firm_scaling_crunchbase_fundraising_core4"
RAW_RESULTS = RAW_DIR / "consolidated_results.csv"
RAW_DIAGNOSTICS = RAW_DIR / "outcome_diagnostics.csv"

OUT_TEX = RESULTS_CLEANED_TEX / "firm_scaling_crunchbase_fundraising_core4.tex"

SAMPLE: Final[str] = "matched_private"
PARAM: Final[str] = "var3"
PARAM_LABEL: Final[str] = r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"


def column_format_padded(n_numeric: int) -> str:
    # tabular* stretching but keep default outer padding (avoid edge clipping).
    return "l" + (r"@{\extracolsep{\fill}}c" * n_numeric)


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def require_columns(df: pd.DataFrame, path: Path, required: set[str]) -> None:
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns {sorted(missing)} in {path}.")


def load_results(path: Path = RAW_RESULTS) -> pd.DataFrame:
    require_file(
        path,
        nonempty=True,
        purpose="Stata exports for core4 Crunchbase table (consolidated_results.csv)",
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


def load_diagnostics(path: Path = RAW_DIAGNOSTICS) -> pd.DataFrame:
    require_file(
        path,
        nonempty=True,
        purpose="Stata exports for core4 Crunchbase table (outcome_diagnostics.csv)",
    )
    df = pd.read_csv(path)
    require_columns(
        df,
        path,
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
    sample: str = SAMPLE,
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
    sample: str = SAMPLE,
) -> float | None:
    sub = diag[(diag["sample_tag"] == sample) & (diag["outcome"] == outcome)].head(1)
    if sub.empty:
        return None
    val = sub.iloc[0].get(field)
    if pd.isna(val):
        return None
    return float(val)


def fmt_int(x: float | None) -> str:
    if x is None:
        return ""
    return f"{int(x):,}"


def fmt_num(x: float | None, *, decimals: int = 3) -> str:
    if x is None:
        return ""
    return f"{x:.{decimals}f}"


def coef_cell(
    rec: pd.Series | None,
    *,
    decimals: int,
    scale_millions: bool = False,
) -> str:
    if rec is None:
        return "--"
    coef = rec.get("coef")
    se = rec.get("se")
    pval = rec.get("pval")
    if pd.isna(coef) or pd.isna(se) or pd.isna(pval) or float(se) == 0:
        return r"\makecell[c]{\textit{omitted}}"

    coef_f = float(coef)
    se_f = float(se)
    p_f = float(pval)

    if scale_millions:
        coef_f /= 1e6
        se_f /= 1e6

    return rf"\makecell[c]{{{coef_f:.{decimals}f}{stars(p_f)}\\({se_f:.{decimals}f})}}"


def header_lines(columns: list[tuple[str, str]]) -> list[str]:
    labels = " & ".join(label for _, label in columns)
    numbers = " & ".join(f"({i})" for i in range(1, len(columns) + 1))
    return [
        TOP,
        r" & " + labels + LB,
        r"\cmidrule(lr){2-" + f"{len(columns) + 1}" + r"}",
        " & " + numbers + LB,
        MID,
    ]


def build_table(results: pd.DataFrame, diag: pd.DataFrame) -> str:
    columns: list[tuple[str, str]] = [
        ("cb_any_raised", r"\makecell[c]{Any USD\\raised}"),
        ("cb_seriesAplus_round", r"\makecell[c]{Series A+\\round}"),
        ("cb_raised_usd_q100", r"\makecell[c]{USD raised\\rank}"),
        ("cb_raised_usd", r"\makecell[c]{USD raised\\(mil)}"),
    ]

    fmt: dict[str, dict] = {
        "cb_any_raised": {"decimals": 3, "mil": False},
        "cb_seriesAplus_round": {"decimals": 3, "mil": False},
        "cb_raised_usd": {"decimals": 2, "mil": True},
        "cb_raised_usd_q100": {"decimals": 3, "mil": False},
    }

    lines: list[str] = [
        PREAMBLE_FLEX + r"\small" + "\n",
        rf"\begin{{tabular*}}{{\linewidth}}{{{column_format_padded(len(columns))}}}",
    ]
    lines.extend(header_lines(columns))
    lines.append(r"\addlinespace[2pt]")

    for panel_label, model in (("Panel A: OLS", "OLS"), ("Panel B: IV", "IV")):
        lines.append(
            rf"\multicolumn{{{len(columns)+1}}}{{@{{}}l}}{{\textbf{{\uline{{{panel_label}}}}}}} {LB}"
        )
        lines.append(r"\addlinespace[2pt]")

        row_cells = [INDENT + PARAM_LABEL]
        for outcome, _ in columns:
            rec = select_row(results, outcome=outcome, model=model)
            row_cells.append(
                coef_cell(
                    rec,
                    decimals=int(fmt[outcome]["decimals"]),
                    scale_millions=bool(fmt[outcome]["mil"]),
                )
            )
        lines.append(" & ".join(row_cells) + LB)

        lines.append(MID)

        # Summary rows:
        # - Pre-Covid Mean: show once (Panel A: OLS) to avoid repetition.
        # - N: show for both OLS and IV (can differ across estimators).
        # - First-stage strength: IV only.
        if model == "OLS":
            pre_cells = ["Pre-Covid Mean"]
            for outcome, _ in columns:
                pre = diag_value(diag, outcome=outcome, field="mean_pre")
                if pre is not None and bool(fmt[outcome]["mil"]):
                    pre /= 1e6
                pre_cells.append(fmt_num(pre, decimals=int(fmt[outcome]["decimals"])))
            lines.append(" & ".join(pre_cells) + LB)

        if model == "IV":
            f_cells = ["KP rk Wald F"]
            for outcome, _ in columns:
                rec = select_row(results, outcome=outcome, model="IV")
                rkf = None if rec is None else rec.get("rkf")
                f_cells.append("" if rkf is None or pd.isna(rkf) else f"{float(rkf):.2f}")
            lines.append(" & ".join(f_cells) + LB)

        n_cells = ["N"]
        for outcome, _ in columns:
            rec = select_row(results, outcome=outcome, model=model)
            nobs = None if rec is None else rec.get("nobs")
            if nobs is None or pd.isna(nobs):
                nobs = diag_value(diag, outcome=outcome, field="n_nonmiss")
            n_cells.append(fmt_int(nobs))
        lines.append(" & ".join(n_cells) + LB)

        if panel_label == "Panel A: OLS":
            lines.append(MID)
        else:
            # Fixed effects (match conventions in firm-level tables)
            lines.append(MID)
            lines.append(" & ".join([r"\textbf{Fixed Effects}", *([""] * len(columns))]) + LB)
            lines.append(" & ".join([INDENT + "Time", *(["$\\checkmark$"] * len(columns))]) + LB)
            lines.append(" & ".join([INDENT + "Firm", *(["$\\checkmark$"] * len(columns))]) + LB)

    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT_TEX)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    results = load_results()
    diag = load_diagnostics()

    ensure_dir(args.out.parent)
    args.out.write_text(build_table(results, diag), encoding="utf-8")
    print(f"Wrote core-4 Crunchbase table → {args.out}")


if __name__ == "__main__":
    main()
