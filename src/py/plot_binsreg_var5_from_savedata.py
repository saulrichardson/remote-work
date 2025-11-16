#!/usr/bin/env python3
"""Format binsreg output into a clean matplotlib figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from project_paths import RESULTS_CLEANED_FIGURES, RESULTS_RAW

SAVED_DATA = RESULTS_RAW / "binsreg_var5_levels.dta"
OUTPUT = RESULTS_CLEANED_FIGURES / "binsreg_var5_levels_python.png"


def load_binsreg_data(path: Path) -> pd.DataFrame:
    df = pd.read_stata(path)
    dots = df[
        [
            "treat_var5",
            "dots_x",
            "dots_fit",
            "CI_l",
            "CI_r",
        ]
    ].dropna(subset=["dots_fit"])
    dots = dots.rename(
        columns={
            "treat_var5": "group",
            "dots_x": "age",
            "dots_fit": "value",
            "CI_l": "ci_low",
            "CI_r": "ci_high",
        }
    )
    return dots


def plot_bins(df: pd.DataFrame, output: Path) -> None:
    palette = {
        "Baseline (pre/low remote)": "#1f77b4",
        "Remote × COVID": "#c44e52",
    }
    markers = {
        "Baseline (pre/low remote)": "o",
        "Remote × COVID": "s",
    }

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for group, sub in df.groupby("group"):
        ax.errorbar(
            sub["age"],
            sub["value"],
            yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]],
            fmt=markers.get(group, "o"),
            color=palette.get(group, "#333333"),
            ecolor=palette.get(group, "#333333"),
            elinewidth=1.2,
            capsize=4,
            markersize=6,
            linestyle="-",
            label=group,
        )

    ax.axhline(0.0, color="#999999", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Firm age (years)")
    ax.set_ylabel("Contribution residual (OLS FE spec)")
    ax.set_title("Startup remote effect (binsreg residuals)")
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=250)
    print(f"✓ Python-styled figure saved to {output}")


def main() -> None:
    dots = load_binsreg_data(SAVED_DATA)
    plot_bins(dots, OUTPUT)


if __name__ == "__main__":
    main()
