#!/usr/bin/env python3
"""Format firm_scaling_core_distance results into a LaTeX table."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import List, Sequence

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
SCRIPTS_DIR = HERE.parent
for path in (PY_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore
from user_productivity.build_baseline_table import (  # type: ignore
    PREAMBLE_FLEX,
    STAR_RULES,
    TOP,
    MID,
    BOTTOM,
)

RESULTS_PATH = RESULTS_RAW / "firm_scaling_core_distance" / "consolidated_results.csv"
OUTPUT_PATH = RESULTS_CLEANED_TEX / "firm_scaling_core_distance.tex"

PARAM_ORDER = ("var3", "var5", "var4")
PARAM_LABEL = {
    "var3": r"$ \text{Remote} \times \mathds{1}(\text{Post}) $",
    "var5": r"$ \text{Remote} \times \mathds{1}(\text{Post}) \times \text{Startup} $",
    "var4": r"$ \mathds{1}(\text{Post}) \times \text{Startup} $",
}

OUTCOMES: Sequence[tuple[str, str, str]] = (
    (
        "core_headcount",
        r"Core Headcount",
        "Total number of employees located inside the firm's designated core CBSAs (ABS+REL filtered).",
    ),
    (
        "noncore_headcount",
        r"Non-Core Headcount",
        "Total employees stationed outside the identified core CBSAs, summing across all other markets.",
    ),
    (
        "headcount_far_050",
        r"Headcount $\geq$ 50 km",
        "Employees working in CBSAs that are at least 50 km away from every core CBSA in that half-year.",
    ),
    (
        "headcount_far_250",
        r"Headcount $\geq$ 250 km",
        "Employees working in CBSAs that sit 250 km or more away from any core CBSA.",
    ),
    (
        "core_share",
        r"Core Share",
        "Share of total firm headcount that remains inside core CBSAs during the half-year.",
    ),
    (
        "noncore_share",
        r"Non-Core Share",
        "Fraction of the workforce located outside the core footprint (complements the core share).",
    ),
    (
        "share_far_050",
        r"Share $\geq$ 50 km",
        "Share of headcount posted 50 km or farther from the closest core CBSA.",
    ),
    (
        "share_far_250",
        r"Share $\geq$ 250 km",
        "Share of headcount assigned to CBSAs located at least 250 km from cores.",
    ),
    (
        "avg_distance_km",
        r"Average Distance (km)",
        "Headcount-weighted average distance from the assigned CBSA to the nearest core CBSA.",
    ),
    (
        "p90_distance_km",
        r"90th Percentile Distance",
        "The 90th percentile of the distance-to-core distribution.",
    ),
    (
        "noncore_core_ratio",
        r"Non-Core/Core Ratio",
        "Ratio of headcount outside cores to headcount inside cores.",
    ),
    (
        "core_minus_noncore",
        r"Core $-$ Non-Core",
        "Difference between core and non-core headcount, positive when cores dominate overall staffing.",
    ),
    (
        "num_noncore_cbsa",
        r"Non-Core CBSAs",
        "Count of distinct non-core CBSAs with any positive headcount, a measure of geographic footprint breadth.",
    ),
    (
        "any_far_050",
        r"Any $\geq$ 50 km",
        "Indicator equal to one if the firm staffs at least one CBSA located 50 km or more from the core footprint.",
    ),
    (
        "any_far_250",
        r"Any $\geq$ 250 km",
        "Indicator equal to one if the firm staffs any CBSA that lies 250 km or more from the core footprint.",
    ),
)


def stars(p: float) -> str:
    if pd.isna(p):
        return ""
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_cell(rec: pd.Series | None) -> str:
    if rec is None or pd.isna(rec["coef"]):
        return "--"
    coef = rec["coef"]
    se = rec["se"]
    return rf"\makecell[c]{{{coef:.3f}{stars(rec['pval'])}\\({se:.3f})}}"


def select_row(df: pd.DataFrame, outcome: str, model: str, param: str | None = None) -> pd.Series | None:
    mask = (df["outcome"] == outcome) & (df["model_type"] == model)
    if param is not None:
        mask &= df["param"] == param
    subset = df.loc[mask]
    if subset.empty:
        return None
    return subset.iloc[0]


def stats_line(rec: pd.Series | None, rkf: bool = False) -> str:
    if rec is None:
        return ""
    parts: List[str] = []
    if not pd.isna(rec.get("pre_mean")):
        parts.append(f"Pre-COVID mean: {rec['pre_mean']:.3f}")
    if not pd.isna(rec.get("nobs")):
        parts.append(f"N: {int(rec['nobs']):,}")
    if rkf and not pd.isna(rec.get("rkf")):
        parts.append(f"KP rk Wald F: {rec['rkf']:.2f}")
    if not parts:
        return ""
    return r"\scriptsize " + "; ".join(parts)


def build_panel(df: pd.DataFrame, model: str, label: str, outcomes: Sequence[tuple[str, str, str]]) -> List[str]:
    lines: List[str] = []
    lines.append(rf"\multicolumn{{4}}{{@{{}}l}}{{\textbf{{\uline{{{label}}}}}}} \\")
    lines.append(r"Outcome & " + " & ".join(PARAM_LABEL[p] for p in PARAM_ORDER) + r" \\")
    lines.append(MID)
    for outcome, pretty, _ in outcomes:
        row = [pretty]
        for param in PARAM_ORDER:
            rec = select_row(df, outcome, model, param)
            row.append(coef_cell(rec))
        lines.append(" & ".join(row) + r" \\")
        stat = stats_line(select_row(df, outcome, model), rkf=(model == "IV"))
        if stat:
            lines.append(rf"& \multicolumn{{3}}{{l}}{{{stat}}}\\")
        lines.append(r"\addlinespace[3pt]")
    lines.append(MID)
    return lines


def build_notes(subset: Sequence[tuple[str, str, str]]) -> str:
    parts = [r"\begin{minipage}{0.95\linewidth}", r"\footnotesize \textit{Outcome definitions:}"]
    for _, pretty, desc in subset:
        parts.append(rf"\textbf{{{pretty}}}: {desc}.")
    parts.append(r"\end{minipage}")
    return "\n".join(parts)


def build_table(df: pd.DataFrame, outcomes: Sequence[tuple[str, str, str]], title: str) -> str:
    lines: List[str] = []
    lines.append(rf"\begin{{table}}[H]\centering\caption{{{title}}}")
    lines.append(PREAMBLE_FLEX)
    lines.append(r"\begin{tabular*}{\linewidth}{@{\extracolsep{\fill}}lccc}")
    lines.append(TOP)
    lines.extend(build_panel(df, "OLS", "Panel A: OLS", outcomes))
    lines.extend(build_panel(df, "IV", "Panel B: IV", outcomes))
    lines.append(BOTTOM)
    lines.append(r"\end{tabular*}")
    lines.append(build_notes(outcomes))
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def wrap_document(body: str) -> str:
    preamble = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{booktabs}",
        r"\usepackage{makecell}",
        r"\usepackage{amsmath}",
        r"\usepackage{dsfont}",
        r"\usepackage{ulem}",
        r"\usepackage{float}",
    ]
    lines = preamble + [r"\begin{document}", body, r"\end{document}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(RESULTS_PATH)
    df = pd.read_csv(RESULTS_PATH)
    ensure_dir(OUTPUT_PATH.parent)

    chunks: List[str] = []
    chunk_size = 4
    for idx in range(0, len(OUTCOMES), chunk_size):
        sub = OUTCOMES[idx : idx + chunk_size]
        title = f"Core Distance Outcomes ({idx//chunk_size + 1})"
        chunks.append(build_table(df, sub, title))

    doc = wrap_document("\n\n".join(chunks))
    OUTPUT_PATH.write_text(doc)
    print(f"Wrote core-distance table → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
