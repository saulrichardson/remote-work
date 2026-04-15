#!/usr/bin/env python3
"""Plot event-study coefficients for remote hires: startups vs established firms."""
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
    df = df[df["event_time"].between(-4, 3)]
    df = df[df["event_time"] != -1]
    df = df[df["event_time"] <= 2]  # plot only through tau = 2

    groups = ["startup", "large"]
    colors = {"startup": "#2b83ba", "large": "#fdae61"}
    labels = {"startup": "Remote startup", "large": "Remote established firm"}
    style_map = {
        "startup": {"elinewidth": 1.4, "capsize": 3.0, "ecolor": colors["startup"], "alpha": 0.9, "markersize": 6},
        "large": {"elinewidth": 1.4, "capsize": 4.0, "ecolor": "#ff9d66", "alpha": 0.9, "markersize": 6},
    }
    x_offset = {"startup": 0.06, "large": -0.06}

    fig, ax = plt.subplots(figsize=(6.0, 4.0), dpi=150)

    # Shaded pre/post bands
    ax.axvspan(-4.5, -0.1, color="#444", alpha=0.05, label="Previous firm")
    ax.axvspan(-0.1, 3.5, color="#2d2d2d", alpha=0.03, label="New firm")
    ax.axvline(0, color="#777", linewidth=0.8, linestyle=":")

    baseline_plotted = False
    for g in groups:
        sub = df[df["group"] == g].sort_values("event_time")

        omitted = (sub["b"] == 0) & (sub["lb"] == 0) & (sub["ub"] == 0)
        sub_plot = sub.loc[~omitted]

        x = sub_plot["event_time"].to_numpy() + x_offset.get(g, 0.0)
        y = sub_plot["b"].to_numpy()
        lb = sub_plot["lb"].to_numpy()
        ub = sub_plot["ub"].to_numpy()
        yerr = [y - lb, ub - y]

        if len(x) > 0:
            kwargs = dict(
                fmt="o",
                linestyle="none",
                color=colors[g],
                markersize=4,
                label=labels[g],
            )
            kwargs.update(style_map.get(g, {}))
            ax.errorbar(x, y, yerr=yerr, **kwargs)

        if not baseline_plotted:
            ax.scatter(-1, 0, color="#555", marker="o", s=26, zorder=4, label=r"Baseline ($\tau$ = -1)")
            baseline_plotted = True

    ax.axhline(0, color="#444", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Half-years relative to hire (τ)")
    ax.set_ylabel("Contribution rank: Δ vs τ = -1")
    ax.set_xticks([-4, -3, -2, 0, 1, 2, 3])
    ax.legend(frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ensure_dir(RESULTS_CLEANED_FIGURES)
    fig.tight_layout()
    fig.savefig(OUTPUT)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
