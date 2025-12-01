#!/usr/bin/env python3
"""Plot event-study coefficients for remote hires: startups vs large firms."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Add shared helpers to path and reuse centralised locations
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_FIGURES, RESULTS_RAW, ensure_dir  # type: ignore

INPUT = RESULTS_RAW / "user_hire_event_study_remote_precovid" / "ols_results.csv"
OUTPUT = RESULTS_CLEANED_FIGURES / "user_hire_event_study_remote_rank.png"


def main() -> None:
    df = pd.read_csv(INPUT)
    df = df[df["outcome"] == "total_contributions_q100"].copy()
    df = df[df["event_time"].between(-4, 4)]
    df = df[df["event_time"] != -1]

    groups = ["startup", "large"]
    colors = {"startup": "#2b83ba", "large": "#fdae61"}
    labels = {"startup": "Remote startup", "large": "Remote large firm"}

    fig, ax = plt.subplots(figsize=(6.0, 4.0), dpi=150)

    for g in groups:
        sub = df[df["group"] == g].sort_values("event_time")
        x = sub["event_time"].to_numpy()
        y = sub["b"].to_numpy()
        yerr = [y - sub["lb"].to_numpy(), sub["ub"].to_numpy() - y]
        ax.errorbar(
            x,
            y,
            yerr=yerr,
            fmt="o-",
            color=colors[g],
            markersize=4,
            linewidth=1.2,
            capsize=3,
            label=labels[g],
        )

    ax.axhline(0, color="#444", linewidth=0.8, linestyle="--")
    ax.axvline(0, color="#777", linewidth=0.6, linestyle=":")
    ax.set_xlabel("Half-years relative to hire (τ)")
    ax.set_ylabel("Contribution rank: Δ vs τ = -1")
    ax.set_xticks([-4, -3, -2, 0, 1, 2, 3, 4])
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ensure_dir(RESULTS_CLEANED_FIGURES)
    fig.tight_layout()
    fig.savefig(OUTPUT)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
