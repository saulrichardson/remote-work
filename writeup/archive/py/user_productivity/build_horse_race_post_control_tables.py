#!/usr/bin/env python3
"""Build Overleaf-style LaTeX table for the canonical post-control horse race."""

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

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW  # noqa: E402

DEFAULT_VARIANT = "precovid"
SPEC_ORDER = ["baseline", "firm_growth", "equity_comp", "firm_growth_equity_comp"]
GROUP_TITLES = ["Baseline", "Firm Growth", "Equity Compensation", "Both"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build post-control horse-race table.")
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default=DEFAULT_VARIANT,
        help="Which user-panel variant to load (default: %(default)s)",
    )
    return parser.parse_args()


def load_results(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def starify(pval: float) -> str:
    if pval < 0.01:
        return "***"
    if pval < 0.05:
        return "**"
    if pval < 0.10:
        return "*"
    return ""


def fmt_num(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1e4 or (0 < abs_v < 1e-2):
        return f"{value:.2e}"
    return f"{value:.2f}"


def fmt_cell(row: pd.Series | None) -> str:
    if row is None:
        return ""
    coef = row.get("coef")
    se = row.get("se")
    pval = row.get("pval")
    if any(pd.isna(v) for v in [coef, se]):
        return ""
    return rf"\makecell[c]{{{fmt_num(float(coef))}{starify(float(pval))}\\({fmt_num(float(se))})}}"


def first_row(df: pd.DataFrame, *, model_type: str, spec: str, param: str) -> pd.Series | None:
    hit = df[(df["model_type"] == model_type) & (df["spec"] == spec) & (df["param"] == param)].head(1)
    if hit.empty:
        return None
    return hit.iloc[0]


def nobs_cell(df: pd.DataFrame, *, model_type: str, spec: str) -> str:
    hit = df[(df["model_type"] == model_type) & (df["spec"] == spec)].head(1)
    if hit.empty or pd.isna(hit.iloc[0]["nobs"]):
        return ""
    return f"{int(hit.iloc[0]['nobs']):,}"


def rkf_cell(df: pd.DataFrame, *, spec: str) -> str:
    hit = df[(df["model_type"] == "IV") & (df["spec"] == spec)].head(1)
    if hit.empty or pd.isna(hit.iloc[0]["rkf"]):
        return ""
    return f"{float(hit.iloc[0]['rkf']):.2f}"


def controls_row(label: str, active_cols: set[int], total_cols: int) -> str:
    marks = [r"\checkmark" if idx in active_cols else "" for idx in range(1, total_cols + 1)]
    return r"\hspace{1em}" + label + " & " + " & ".join(marks) + r" \\"


def build_table(df_base: pd.DataFrame, df_pair: pd.DataFrame) -> str:
    total_cols = 8
    colspec = "@{}l" + "c" * total_cols + "@{}"

    lines: list[str] = [
        "% Auto-generated block: post-control horse race",
        r"{\centering",
        r"\resizebox{\linewidth}{!}{%",
        rf"\begin{{tabular}}{{{colspec}}}",
        r"\toprule",
        r" & \multicolumn{8}{c}{Contribution Rank} \\",
        r"\cmidrule(lr){2-9}",
        r" & \multicolumn{4}{c}{Baseline FE} & \multicolumn{4}{c}{Pair FE} \\",
        r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
        r" & (1) & (2) & (3) & (4) & (5) & (6) & (7) & (8) \\",
        " & " + " & ".join(GROUP_TITLES + GROUP_TITLES) + r" \\",
        r"\midrule",
        r"\multicolumn{9}{@{}l}{\textbf{\uline{Panel A: OLS}}} \\",
        r"\addlinespace[2pt]",
    ]

    for param, label in [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
    ]:
        cells = [fmt_cell(first_row(df_base, model_type="OLS", spec=spec, param=param)) for spec in SPEC_ORDER]
        cells += [fmt_cell(first_row(df_pair, model_type="OLS", spec=spec, param=param)) for spec in SPEC_ORDER]
        lines.append(r"\hspace{1em}" + label + " & " + " & ".join(cells) + r" \\")

    lines.extend(
        [
            r"\midrule",
            "N & "
            + " & ".join([nobs_cell(df_base, model_type="OLS", spec=spec) for spec in SPEC_ORDER]
                         + [nobs_cell(df_pair, model_type="OLS", spec=spec) for spec in SPEC_ORDER])
            + r" \\",
            r"\midrule",
            r"\multicolumn{9}{@{}l}{\textbf{\uline{Panel B: IV}}} \\",
            r"\addlinespace[2pt]",
        ]
    )

    for param, label in [
        ("var3", r"$ \text{Remote} \times \mathds{1}(\text{Post}) $"),
        ("var5", r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $"),
    ]:
        cells = [fmt_cell(first_row(df_base, model_type="IV", spec=spec, param=param)) for spec in SPEC_ORDER]
        cells += [fmt_cell(first_row(df_pair, model_type="IV", spec=spec, param=param)) for spec in SPEC_ORDER]
        lines.append(r"\hspace{1em}" + label + " & " + " & ".join(cells) + r" \\")

    lines.extend(
        [
            r"\midrule",
            "N & "
            + " & ".join([nobs_cell(df_base, model_type="IV", spec=spec) for spec in SPEC_ORDER]
                         + [nobs_cell(df_pair, model_type="IV", spec=spec) for spec in SPEC_ORDER])
            + r" \\",
            r"KP\,rk Wald F & "
            + " & ".join([rkf_cell(df_base, spec=spec) for spec in SPEC_ORDER]
                         + [rkf_cell(df_pair, spec=spec) for spec in SPEC_ORDER])
            + r" \\",
            r"\midrule",
            r"\textbf{Fixed Effects} &  &  &  &  &  &  &  &  \\",
            controls_row("Time", set(range(1, 9)), total_cols),
            controls_row("Firm", {1, 2, 3, 4}, total_cols),
            controls_row("Individual", {1, 2, 3, 4}, total_cols),
            controls_row(r"Firm $\times$ Individual", {5, 6, 7, 8}, total_cols),
            r"\midrule",
            r"\textbf{Controls} &  &  &  &  &  &  &  &  \\",
            controls_row("Firm Growth", {2, 4, 6, 8}, total_cols),
            controls_row("Equity Compensation", {3, 4, 7, 8}, total_cols),
            r"\bottomrule",
            r"\end{tabular}",
            r"}",
            r"}",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    variant = args.variant

    base_path = RESULTS_RAW / f"user_horse_race_post_control_baseline_{variant}" / "consolidated_results.csv"
    pair_path = RESULTS_RAW / f"user_horse_race_post_control_pair_{variant}" / "consolidated_results.csv"
    out_path = RESULTS_CLEANED_TEX / f"user_horse_race_post_control_{variant}.tex"

    df_base = load_results(base_path)
    df_pair = load_results(pair_path)
    table = build_table(df_base, df_pair)
    out_path.write_text(table)
    print(out_path)


if __name__ == "__main__":
    main()
