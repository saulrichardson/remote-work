#!/usr/bin/env python3
"""Build a compact LaTeX table for the remote-hire event study (rank outcome)."""
from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
from scipy import stats

# Centralise path handling
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW, ensure_dir  # type: ignore

INPUT = RESULTS_RAW / "user_hire_event_study_remote_precovid" / "ols_results.csv"
SAMPLE_STATS = RESULTS_RAW / "user_hire_event_study_remote_precovid" / "sample_stats.csv"
OUTPUT = RESULTS_CLEANED_TEX / "user_hire_event_study_remote_rank.tex"

STAR_RULES = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def stars(p: float) -> str:
    for cut, sym in STAR_RULES:
        if p < cut:
            return sym
    return ""


def main() -> None:
    df = pd.read_csv(INPUT)
    df = df[(df["outcome"] == "total_contributions_q100") & (df["model"] == "OLS")].copy()
    df["se"] = (df["ub"] - df["b"]) / 1.96
    df["t"] = df["b"] / df["se"]
    df["p"] = 2 * stats.norm.sf(df["t"].abs())

    df = df[df["event_time"].isin([-4, -3, -2, 0, 1, 2, 3])]
    df = df.sort_values("event_time")

    stats_df = pd.read_csv(SAMPLE_STATS)
    if "dest_startup" not in stats_df.columns:
        raise RuntimeError("sample_stats missing dest_startup column (re-run Stata export)")
    stats_df["group"] = stats_df["dest_startup"].map({1: "startup", 0: "large"})
    stats_df = stats_df.set_index("group")

    rows = []
    for evt in [-4, -3, -2, 0, 1, 2, 3]:
        sub = df[df["event_time"] == evt]
        row = {"evt": evt}
        for g in ["startup", "large"]:
            r = sub[sub["group"] == g]
            if r.empty or ((r["b"] == 0).all() and (r["ub"] == 0).all()):
                row[g] = "--"
            else:
                r = r.iloc[0]
                row[g] = f"{r.b:.2f}{stars(r.p)} ({r.se:.2f})"
        rows.append(row)

    pre_startup = stats_df.loc["startup", "pre_mean"]
    pre_large = stats_df.loc["large", "pre_mean"]
    n_startup = int(stats_df.loc["startup", "N_group"])
    n_large = int(stats_df.loc["large", "N_group"])

    lines = [
        "% Auto-generated; do not edit",
        r"\begin{tabular*}{\linewidth}{@{}l@{\extracolsep{\fill}}cc@{}}",
        r"\toprule",
        r" & Remote startup & Remote established \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(rf"$\tau$ = {row['evt']:>+d} & {row['startup']} & {row['large']} \\")

    lines.extend(
        [
            r"\midrule",
            rf"Pre-hire mean ($\tau$=-1) & {pre_startup:.2f} & {pre_large:.2f} \\",
            rf"N & {n_startup:,} & {n_large:,} \\",
            r"\midrule",
            r"\textbf{Fixed effects} & & \\",
            r"\hspace{1em}Time & $\checkmark$ & $\checkmark$ \\",
            r"\hspace{1em}Firm & $\checkmark$ & $\checkmark$ \\",
            r"\hspace{1em}Individual & $\checkmark$ & $\checkmark$ \\",
            r"\bottomrule",
            r"\end{tabular*}",
        ]
    )

    ensure_dir(OUTPUT.parent)
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
