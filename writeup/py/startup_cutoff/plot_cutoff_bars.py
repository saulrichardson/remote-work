#!/usr/bin/env python3
"""Plot OLS startup-interaction coefficients across cutoff sweeps."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_FIGURES, RESULTS_RAW, ensure_dir  # noqa: E402
from plot_style import (  # noqa: E402
    FIGSIZE,
    SERIES_COLOR,
    SECONDARY_COLOR,
    apply_mpl_defaults,
    apply_standard_figure_layout,
    compute_padded_limits,
    errorbar_kwargs,
    style_axes,
)
apply_mpl_defaults()
plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{palatino}",
})

CUTOFFS: tuple[int, ...] = (5, 7, 10, 12, 15)
CUTOFF_LABELS = tuple(f"$\\leq {c}$" for c in CUTOFFS)
Y_LABEL = r"$\beta_{ \text{Remote} \times \mathbf{1}(\text{Post}) \times \text{Startup} }$"

CLEANED_DIR = PROJECT_ROOT / "results" / "cleaned" / "startup_cutoff"

PANELS: tuple[dict[str, str], ...] = (
    {
        "panel": "Panel A",
        "dataset": "user",
        "outcome": "total_contributions_q100",
        "title": "Contribution Rank (Total)",
        "filename": "startup_cutoff_bars_total_contributions_q100.png",
    },
    {
        "panel": "Panel B",
        "dataset": "firm",
        "outcome": "growth_rate_we",
        "title": "Firm Growth Rate",
        "filename": "startup_cutoff_bars_growth_rate_we.png",
    },
)

COMBINED_FILENAME = "startup_cutoff_bars_main_panels.png"


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    df = pd.read_csv(path)
    df["cutoff"] = df["cutoff"].astype(int)
    return df


def _series(df: pd.DataFrame, *, outcome: str) -> pd.DataFrame:
    subset = df[
        (df["model_type"] == "OLS")
        & (df["param"] == "var5")
        & (df["outcome"] == outcome)
    ].copy()
    if subset.empty:
        raise ValueError(f"No OLS var5 rows found for outcome={outcome}")
    subset = subset.set_index("cutoff").reindex(CUTOFFS).reset_index()
    if subset["coef"].isna().any():
        missing = subset[subset["coef"].isna()]["cutoff"].tolist()
        raise ValueError(f"Missing coefficients for cutoffs: {missing}")
    return subset


CI_Z = 1.96


def _plot_coef_series(
    ax: plt.Axes,
    *,
    coefs: np.ndarray,
    ses: np.ndarray,
    show_ylabel: bool = True,
) -> None:
    x = np.arange(len(coefs), dtype=float)
    half = CI_Z * ses
    bars = ax.bar(
        x,
        coefs,
        width=0.55,
        color="#e0e0e0",
        edgecolor="#4a4a4a",
        linewidth=0.9,
        zorder=2,
    )
    errs = np.vstack([half, half])
    kwargs = errorbar_kwargs("#1f1f1f").copy()
    kwargs["fmt"] = "o"
    kwargs["linestyle"] = "none"
    kwargs["capsize"] = 4
    kwargs["elinewidth"] = 1.2
    kwargs["markersize"] = 5.3
    kwargs["zorder"] = 3
    ax.errorbar(x, coefs, yerr=errs, **kwargs)
    ax.axhline(0.0, color="#555555", linewidth=0.9, linestyle="--", alpha=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(CUTOFF_LABELS)
    if show_ylabel:
        ax.set_ylabel(Y_LABEL)
    ax.set_xlabel("Startup Age Cutoff")

    spread = np.concatenate([coefs - CI_Z * ses, coefs + CI_Z * ses, [0.0]])
    ymin, ymax = compute_padded_limits(spread, pad_ratio=0.2)
    ax.set_ylim(ymin, ymax)

    style_axes(ax)
    for label in ax.get_xticklabels():
        label.set_rotation(0)


def _single_figure(
    *,
    coefs: np.ndarray,
    ses: np.ndarray,
    output: Path,
) -> None:
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _plot_coef_series(
        ax,
        coefs=coefs,
        ses=ses,
    )
    apply_standard_figure_layout(fig)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def _plot_panels(
    specs: Sequence[dict[str, str]],
    data: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    output: Path,
) -> None:
    fig, axes = plt.subplots(1, len(specs), figsize=(11.5, 4.6), sharey=False)
    if len(specs) == 1:
        axes = [axes]
    for idx, (ax, spec) in enumerate(zip(axes, specs)):
        coefs, ses = data[spec["panel"]]
        show_ylabel = idx == 0
        _plot_coef_series(
            ax,
            coefs=coefs,
            ses=ses,
            show_ylabel=show_ylabel,
        )
    apply_standard_figure_layout(fig)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-csv",
        type=Path,
        default=RESULTS_RAW
        / "user_productivity_startup_cutoff_sweep_precovid"
        / "consolidated_results.csv",
        help="Path to the user cutoff sweep CSV",
    )
    parser.add_argument(
        "--firm-csv",
        type=Path,
        default=RESULTS_RAW
        / "firm_scaling_startup_cutoff_sweep"
        / "consolidated_results.csv",
        help="Path to the firm cutoff sweep CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_CLEANED_FIGURES,
        help="Directory for output PNGs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dir(args.output_dir)
    ensure_dir(CLEANED_DIR)

    user_df = _load(args.user_csv)
    firm_df = _load(args.firm_csv)

    dataframes = {"user": user_df, "firm": firm_df}
    figure_data: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    for spec in PANELS:
        df = dataframes[spec["dataset"]]
        subset = _series(df, outcome=spec["outcome"])
        coefs = subset["coef"].to_numpy(dtype=float)
        ses = subset["se"].to_numpy(dtype=float)
        figure_data[spec["panel"]] = (coefs, ses)

        cleaned = subset[["cutoff", "coef", "se"]].copy()
        cleaned["ci95_lower"] = cleaned["coef"] - CI_Z * cleaned["se"]
        cleaned["ci95_upper"] = cleaned["coef"] + CI_Z * cleaned["se"]
        cleaned["dataset"] = spec["dataset"]
        cleaned["outcome"] = spec["outcome"]
        cleaned["label"] = Y_LABEL
        cleaned_path = CLEANED_DIR / f"{spec['dataset']}_{spec['outcome']}_summary.csv"
        cleaned.to_csv(cleaned_path, index=False)

        single_output = args.output_dir / spec["filename"]
        _single_figure(
            coefs=coefs,
            ses=ses,
            output=single_output,
        )
        print(f"Saved {spec['panel']} figure to {single_output}")

    output_path = args.output_dir / COMBINED_FILENAME
    _plot_panels(PANELS, figure_data, output=output_path)
    print(f"Saved two-panel startup cutoff figure to {output_path}")


if __name__ == "__main__":
    main()
