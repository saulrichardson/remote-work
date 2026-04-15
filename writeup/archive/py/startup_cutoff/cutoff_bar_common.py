#!/usr/bin/env python3
"""Shared rendering helpers for the active startup-cutoff figures."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
WRITEUP_PY = PROJECT_ROOT / "writeup" / "py"
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(WRITEUP_PY) not in sys.path:
    sys.path.insert(0, str(WRITEUP_PY))
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_FIGURES, RESULTS_RAW, ensure_dir  # noqa: E402
from plot_style import (  # noqa: E402
    FIGSIZE,
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


USER_INPUT = (
    RESULTS_RAW
    / "03_startup_cutoff_bars_total_contributions_q100"
    / "user_productivity"
    / "consolidated_results.csv"
)
FIRM_INPUT = (
    RESULTS_RAW
    / "04_startup_cutoff_bars_growth_rate_we"
    / "firm_scaling"
    / "consolidated_results.csv"
)


def build_total_contributions_q100(
    *,
    input_csv: Path = USER_INPUT,
    output_dir: Path = RESULTS_CLEANED_FIGURES,
) -> Path:
    ensure_dir(output_dir)
    subset = _series(_load(input_csv), outcome="total_contributions_q100")
    output = output_dir / "startup_cutoff_bars_total_contributions_q100.png"
    _single_figure(
        coefs=subset["coef"].to_numpy(dtype=float),
        ses=subset["se"].to_numpy(dtype=float),
        output=output,
    )
    print(f"Saved Panel A figure to {output}")
    return output


def build_growth_rate_we(
    *,
    input_csv: Path = FIRM_INPUT,
    output_dir: Path = RESULTS_CLEANED_FIGURES,
) -> Path:
    ensure_dir(output_dir)
    subset = _series(_load(input_csv), outcome="growth_rate_we")
    output = output_dir / "startup_cutoff_bars_growth_rate_we.png"
    _single_figure(
        coefs=subset["coef"].to_numpy(dtype=float),
        ses=subset["se"].to_numpy(dtype=float),
        output=output,
    )
    print(f"Saved Panel B figure to {output}")
    return output


if __name__ == "__main__":
    raise SystemExit(
        "Use writeup/py/startup_cutoff/03_startup_cutoff_bars_total_contributions_q100.py "
        "or writeup/py/startup_cutoff/04_startup_cutoff_bars_growth_rate_we.py."
    )
