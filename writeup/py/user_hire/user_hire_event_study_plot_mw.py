#!/usr/bin/env python3
"""Mini-writeup styled plot for remote-hire event study (rank outcome)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Project paths
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_RAW, RESULTS_CLEANED_FIGURES, ensure_dir  # type: ignore  # noqa: E402
from plot_style import (  # type: ignore  # noqa: E402
    apply_mpl_defaults,
    apply_standard_figure_layout,
    style_axes,
    set_integer_xticks,
    compute_padded_limits,
    SERIES_COLOR,
    SECONDARY_COLOR,
    ERROR_COLOR,
    FIGSIZE,
    FIG_DPI,
    errorbar_kwargs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot hire event-study (remote startup vs established) in mini-writeup style.")
    parser.add_argument(
        "--input",
        type=Path,
        default=RESULTS_RAW / "user_hire_event_study_remote_precovid" / "ols_results.csv",
        help="OLS results CSV from Stata export",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_CLEANED_FIGURES / "user_hire_event_study_remote_rank_mw.png",
        help="Output PNG",
    )
    parser.add_argument(
        "--outcome",
        default="total_contributions_q100",
        help="Outcome column to plot",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply_mpl_defaults()

    if not args.input.exists():
        raise FileNotFoundError(f"Missing input CSV: {args.input}")

    df = pd.read_csv(args.input)
    df = df[(df["outcome"] == args.outcome) & (df["model"].str.upper() == "OLS")]
    df = df[df["event_time"].between(-4, 3)]
    df = df[df["event_time"] != -1]
    df = df[df["event_time"] <= 2]  # plot only through tau = 2
    df = df.sort_values(["group", "event_time"])

    if df.empty:
        raise RuntimeError("No rows found after filtering; did Stata export run?")

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    style_axes(ax)

    color_map = {"startup": SERIES_COLOR, "large": SECONDARY_COLOR}
    label_map = {"startup": "Remote startup", "large": "Remote established firm"}
    style_map = {
        "startup": {"elinewidth": 1.4, "capsize": 3.5, "ecolor": SERIES_COLOR, "alpha": 0.9, "markersize": 6},
        "large": {"elinewidth": 1.4, "capsize": 3.5, "ecolor": "#ff9d66", "alpha": 0.9, "markersize": 6},
    }
    x_offset = {"startup": 0.06, "large": -0.06}

    ymin, ymax = compute_padded_limits(
        [df["lb"], df["ub"]],
        pad_ratio=0.08,
        min_span=0.2,
        lower_bound=None,
        upper_bound=None,
    )

    baseline_plotted = False
    for group in ["startup", "large"]:
        sub = df[df["group"] == group].copy()
        if sub.empty:
            continue

        # Treat rows with b=lb=ub=0 as omitted; do not draw lines through them.
        omitted = (sub["b"] == 0) & (sub["lb"] == 0) & (sub["ub"] == 0)
        sub_plot = sub.loc[~omitted].sort_values("event_time")

        x = sub_plot["event_time"].to_numpy(dtype=float) + x_offset.get(group, 0.0)
        y = sub_plot["b"].to_numpy(dtype=float)
        lower = sub_plot["lb"].to_numpy(dtype=float)
        upper = sub_plot["ub"].to_numpy(dtype=float)
        err = np.vstack((y - lower, upper - y))

        kwargs = errorbar_kwargs(color_map.get(group, SERIES_COLOR))
        kwargs.update(style_map.get(group, {}))
        kwargs["fmt"] = "o"
        kwargs["linestyle"] = "none"
        kwargs["label"] = label_map.get(group, group.title())
        ax.errorbar(x, y, yerr=err, **kwargs)

        # Plot a single baseline point at tau = -1 (y=0) once
        if not baseline_plotted:
            ax.scatter(-1, 0, color="#555", marker="o", s=28, zorder=4, label=r"Baseline ($\tau$ = -1)")
            baseline_plotted = True

    ax.axhline(0, color=ERROR_COLOR, linewidth=1.0, linestyle="--", zorder=1)
    ax.axvline(0, color="#777", linewidth=0.9, linestyle=":")

    set_integer_xticks(ax, df["event_time"].to_numpy())
    ax.set_xlabel("Half-years relative to hire (τ)")
    ax.set_ylabel("Contribution rank: Δ vs τ = -1")
    ax.set_ylim(ymin, ymax)
    ax.legend(frameon=False)

    apply_standard_figure_layout(fig)
    ensure_dir(args.output.parent)
    fig.savefig(args.output, bbox_inches="tight")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
