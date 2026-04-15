#!/usr/bin/env python3
"""Generate a LaTeX table for firm-scaling location HHI results."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "results" / "raw"
CLEAN_DIR = ROOT / "results" / "cleaned"
SPEC = "firm_scaling_location_hhi"

PARAMS = ["var3", "var5", "var4"]
PARAM_LABEL = {
    "var3": "Remote x Post",
    "var5": "Remote x Post x Startup",
    "var4": "Post x Startup",
}

OUTCOME_LABEL = "HHI (0-1)"
STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]

PREAMBLE = dedent(
    r"""{\scriptsize%
\setlength{\tabcolsep}{3pt}%
\renewcommand{\arraystretch}{0.95}%
\begin{adjustbox}{max width=\linewidth}%
"""
)
POSTAMBLE = r"\end{adjustbox}}"
ROW_BREAK = r" \\"  # LaTeX row terminator


def load_results() -> pd.DataFrame:
    path = RAW_DIR / SPEC / "consolidated_results.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def coef_entry(row: pd.Series | None) -> str:
    if row is None:
        return ""
    return f"{row['coef']:.3f}{stars(row['pval'])} ({row['se']:.3f})"


def grab_row(df: pd.DataFrame, model: str, param: str) -> pd.Series | None:
    sub = df[
        (df["model_type"] == model)
        & (df["param"] == param)
        & (df["outcome"] == "hhi")
    ]
    return None if sub.empty else sub.iloc[0]


def stat_value(df: pd.DataFrame, model: str, field: str) -> str:
    sub = df[
        (df["model_type"] == model)
        & (df["outcome"] == "hhi")
        & (df["param"] == "var3")
    ]
    if sub.empty:
        return ""
    val = sub.iloc[0].get(field)
    if pd.isna(val):
        return ""
    if field == "nobs":
        return f"{int(val):,}"
    if field == "pre_mean":
        return f"{val:.3f}"
    if field == "rkf":
        return f"{val:.2f}"
    return str(val)


def build_panel(df: pd.DataFrame, model: str, heading: str, include_kp: bool = False) -> list[str]:
    lines = [f"\\multicolumn{{2}}{{l}}{{\\textit{{{heading}}}}}" + ROW_BREAK]
    for param in PARAMS:
        row = grab_row(df, model, param)
        lines.append(" & ".join([PARAM_LABEL[param], coef_entry(row)]) + ROW_BREAK)

    lines.append("\\midrule")
    lines.append(" & ".join(["N", stat_value(df, model, "nobs")]) + ROW_BREAK)
    lines.append(" & ".join(["Pre-mean", stat_value(df, model, "pre_mean")]) + ROW_BREAK)
    if include_kp:
        lines.append(" & ".join(["KP rk Wald F", stat_value(df, model, "rkf")]) + ROW_BREAK)
    return lines


def build_table(df: pd.DataFrame) -> str:
    column_spec = "lc"
    body = [
        "\\toprule",
        " & ".join(["Parameter", OUTCOME_LABEL]) + ROW_BREAK,
        "\\midrule",
        *build_panel(df, "OLS", "Panel A: OLS"),
        "\\midrule",
        *build_panel(df, "IV", "Panel B: IV", include_kp=True),
        "\\bottomrule",
    ]

    lines = [
        r"\begin{table}[H]",
        "\\centering",
        "\\caption{Firm Scaling — Location Concentration (HHI)}",
        "\\label{tab:firm_scaling_location_hhi}",
        PREAMBLE.strip(),
        rf"\begin{{tabular}}{{{column_spec}}}",
        *body,
        "\\end{tabular}",
        POSTAMBLE,
        r"\end{table}",
    ]
    return "\n".join(lines)


def main() -> None:
    df = load_results()
    tex = build_table(df)
    out_path = CLEAN_DIR / "firm_scaling_location_hhi_table.tex"
    out_path.write_text(tex + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
