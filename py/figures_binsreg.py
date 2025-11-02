#!/usr/bin/env python3
"""Generate the mini-writeup figures using binsreg binscatters.

This script reuses the legacy ``py/figures.py`` workflow, but
monkey-patches its binscatter helper so that the plotted points come
from the `binsreg` package (Cattaneo et al.).  That gives us the same
behaviour as the modern Stata `binsreg` command while keeping the rest
of the figure pipeline unchanged.  Swap between implementations by
calling either ``figures.py`` (legacy quantile-midpoint approach) or
this module (binsreg-based approach).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from binsreg import binsreg
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "binsreg is not installed. Run `pip install binsreg` inside the "
        "project virtualenv before executing py/figures_binsreg.py."
    ) from exc

import numpy as np
import pandas as pd

from project_paths import PY_DIR

if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

# Legacy figure script (relies on _plot_bins_reg helper we override)
import figures as legacy


def _binsreg_points(df: pd.DataFrame, x: str, y: str, nbins: int) -> tuple[np.ndarray, np.ndarray]:
    """Return within-bin means for x and fitted y using binsreg."""
    df_valid = df[[x, y]].dropna()
    if df_valid.empty:
        raise ValueError("No observations left after filtering NaNs")

    unique_x = df_valid[x].nunique()
    if unique_x < 2:
        raise ValueError("Insufficient variation in x for binsreg")

    def run_binsreg(nbins_override: int | None):
        return binsreg(
            df_valid[y].to_numpy(),
            df_valid[x].to_numpy(),
            nbins=nbins_override,
            noplot=True,
            nsims=0,
            binsmethod="dpi",
            binspos="qs",
        )

    res = run_binsreg(None)
    dots = res.data_plot[0].dots

    if dots is None or dots.empty:
        nbins_use = min(max(1, unique_x - 1), nbins)
        res = run_binsreg(nbins_use)
        dots = res.data_plot[0].dots
        if dots is None or dots.empty:
            raise RuntimeError("binsreg failed to produce dots even after fallback")

    return dots["x"].to_numpy(), dots["fit"].to_numpy()


def _plot_bins_reg(
    data: pd.DataFrame,
    x: str,
    y: str,
    *,
    q: int,
    xlabel: str,
    ylabel: str,
    file_stem: str,
    split_col: str | None = None,
    y_limits: tuple[float, float] | None = None,
):
    """Drop-in replacement for ``figures._plot_bins_reg`` using binsreg."""

    import matplotlib.pyplot as plt
    import statsmodels.formula.api as smf

    fig, ax = plt.subplots(figsize=legacy.FIGSIZE, dpi=legacy.FIG_DPI)
    legacy._style_axes(ax)  # type: ignore[attr-defined]

    groups = data.groupby(split_col) if split_col else [(None, data)]
    for key, grp in groups:
        grp_valid = grp.dropna(subset=[x, y])
        if len(grp_valid) < 3 or grp_valid[x].nunique() < 2:
            continue

        xs, ys = _binsreg_points(grp_valid, x, y, nbins=q)
        colour = legacy.COLOURS.get(key, "black")  # type: ignore[attr-defined]
        label_bs = (
            f"{'Remote' if key else 'Non‑remote'} (Binscatter)"
            if split_col
            else "Binscatter"
        )
        ax.plot(
            xs,
            ys,
            "o",
            linewidth=2.2,
            color=colour,
            label=label_bs,
            markeredgecolor="white",
            markeredgewidth=0.5,
        )

        model = smf.ols(f"{y} ~ {x}", data=grp_valid).fit()
        x_vals = np.linspace(grp_valid[x].min(), grp_valid[x].max(), 200)
        y_vals = model.predict(pd.DataFrame({x: x_vals}))
        label_ols = (
            f"{'Remote' if key else 'Non‑remote'} (OLS)"
            if split_col
            else "OLS"
        )
        ax.plot(x_vals, y_vals, linewidth=2.2, color=colour, label=label_ols)

        slope = model.params[x]
        se = model.bse[x]
        r2 = model.rsquared
        anno = rf"$\beta = {slope:.2f}\;({se:.2f})$" "\n" rf"$R^2 = {r2:.2f}$"

        if x == "teleworkable" and y == "remote":
            ax.text(
                0.05,
                0.95,
                anno,
                transform=ax.transAxes,
                fontsize=11,
                verticalalignment="top",
                horizontalalignment="left",
                color=colour,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.6, edgecolor=colour),
            )
        elif x in {"age", "log_age"} and y == "remote" and split_col is None:
            ax.text(
                0.95,
                0.95,
                anno,
                transform=ax.transAxes,
                fontsize=11,
                verticalalignment="top",
                horizontalalignment="right",
                color=colour,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.6, edgecolor=colour),
            )

    ax.tick_params(axis="both", labelsize=12)
    ax.set_xlabel(xlabel, fontsize=14)
    ax.set_ylabel(ylabel, fontsize=14)
    limits = (
        y_limits
        if y_limits is not None
        else legacy.compute_padded_limits(data[y].dropna())
    )
    ax.set_ylim(*limits)
    legacy.apply_standard_figure_layout(fig)
    fig.savefig(legacy.OUTPUT_DIR / f"{file_stem}.png", dpi=legacy.FIG_DPI, facecolor="white")
    plt.close(fig)


def main(worker_file: Path) -> None:
    legacy._plot_bins_reg = _plot_bins_reg  # type: ignore[attr-defined]
    legacy.main(worker_file=worker_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate figures using binsreg binscatters")
    parser.add_argument(
        "--worker-file",
        type=Path,
        default=legacy.WORKER_FILE,  # type: ignore[attr-defined]
        help="Worker-level CSV sample (default: precovid)",
    )
    args = parser.parse_args()
    main(worker_file=args.worker_file)
