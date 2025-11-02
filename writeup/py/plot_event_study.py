#!/usr/bin/env python3
"""Plot event-study coefficients from exported CSVs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
PY_DIR = PROJECT_ROOT / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


from plot_style import (  # noqa: E402  pylint: disable=wrong-import-position
    EVENT_YLIMS,
    EVENT_YTICKS,
    FIGSIZE,
    FIG_DPI,
    SERIES_COLOR,
    CONTROL_COLOR,
    apply_mpl_defaults,
    apply_standard_figure_layout,
    errorbar_kwargs,
    style_axes,
    compute_padded_limits,
)

apply_mpl_defaults()

DEFAULT_CLIP_QUANTILE = 0.0


def _sort_columns(df: pd.DataFrame) -> list[str]:
    """Return preferred sort columns in priority order."""
    order: list[str] = []
    if "event_time" in df.columns:
        order.append("event_time")
    for col in ("period", "yh"):
        if col in df.columns and col not in order:
            order.append(col)
    return order



def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Create an event-study plot from exported CSVs")
    parser.add_argument("--ols", required=True, type=Path, help="Path to OLS CSV (exported by Stata)")
    parser.add_argument("--iv", type=Path, help="Optional IV CSV to overlay")
    parser.add_argument("--output", required=True, type=Path, help="Output PNG path")
    parser.add_argument("--title")
    parser.add_argument("--ylabel", default="Outcome")
    parser.add_argument("--xlabel", default="Event time")
    parser.add_argument("--ylim", nargs=2, type=float, help="Optional y-axis limits: ymin ymax")
    parser.add_argument("--legend-loc", default="none")
    parser.add_argument(
        "--series",
        choices=["ols", "iv", "both"],
        default="both",
        help="Which estimator(s) to plot when IV data is supplied",
    )
    parser.add_argument(
        "--clip-quantile",
        type=float,
        default=DEFAULT_CLIP_QUANTILE,
        help="Trim axis limits to the (q, 1-q) quantiles of the plotted confidence bands; set 0 to disable",
    )
    parser.add_argument(
        "--limit-ols",
        action="append",
        type=Path,
        default=None,
        help="Additional OLS CSV files to include when computing shared y-axis limits",
    )
    return parser.parse_args()



def _ensure_dataframe(path: Path, estimator: str | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    df = pd.read_csv(path)
    if estimator and "estimator" in df.columns:
        df = df[df["estimator"].str.upper() == estimator.upper()].copy()
    return df



def _prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, int | None]:
    df = df.copy()
    sort_cols = _sort_columns(df)
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    for col in ("b", "lb", "ub"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "event_time" in df.columns:
        df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    if "yh" in df.columns:
        df["yh"] = df["yh"].astype(str)

    if "event_time" in df.columns and df["event_time"].notna().all():
        df["_x"] = df["event_time"].to_numpy(dtype=float)
    else:
        df["_x"] = np.arange(len(df), dtype=float)

    omitted_mask = df.get("omitted", False)
    if isinstance(omitted_mask, pd.Series):
        omitted_mask = omitted_mask.astype(bool)
    else:
        omitted_mask = pd.Series(False, index=df.index)

    omitted_idx = df.index[omitted_mask].tolist()
    baseline_idx = omitted_idx[0] if omitted_idx else None
    if baseline_idx is not None:
        df.loc[baseline_idx, ["b", "lb", "ub"]] = np.nan

    return df, baseline_idx


def _load_ols_bounds(path: Path) -> np.ndarray | None:
    df = _ensure_dataframe(path, estimator="OLS")
    df, _ = _prepare(df)
    if df.empty:
        return None
    return df[["lb", "ub"]].to_numpy(dtype=float)



def _quantile_bounds(arrays: Iterable[np.ndarray], q: float) -> tuple[float, float] | None:
    values = [np.asarray(arr, dtype=float).ravel() for arr in arrays]
    if not values:
        return None
    stacked = np.concatenate(values)
    stacked = stacked[~np.isnan(stacked)]
    if stacked.size == 0:
        return None
    lo = np.nanquantile(stacked, q)
    hi = np.nanquantile(stacked, 1 - q)
    if not (np.isfinite(lo) and np.isfinite(hi) and hi > lo):
        return None
    return float(lo), float(hi)



def _plot_series(
    ax: plt.Axes,
    df: pd.DataFrame,
    *,
    label: str,
    color: str,
    clip_bounds: tuple[float, float] | None = None,
    baseline_idx: int | None = None,
) -> np.ndarray:
    y = df["b"].to_numpy(dtype=float)
    lower = df["lb"].to_numpy(dtype=float)
    upper = df["ub"].to_numpy(dtype=float)
    x = df["_x"].to_numpy(dtype=float)

    y_plot = y.copy()
    lower_clipped = lower.copy()
    upper_clipped = upper.copy()

    if clip_bounds is not None:
        lo_bound, hi_bound = clip_bounds
        y_plot = np.clip(y_plot, lo_bound, hi_bound)
        lower_clipped = np.clip(lower_clipped, lo_bound, hi_bound)
        upper_clipped = np.clip(upper_clipped, lo_bound, hi_bound)

    lower_err = y_plot - lower_clipped
    upper_err = upper_clipped - y_plot

    err = np.vstack((lower_err, upper_err))
    err = np.nan_to_num(err, nan=0.0)
    err[err < 0.0] = 0.0

    kwargs = errorbar_kwargs(color).copy()
    kwargs["fmt"] = "o"
    ax.errorbar(x, y_plot, yerr=err, label=label, **kwargs)

    if baseline_idx is not None:
        marker_y = 0.0
        if clip_bounds is not None:
            marker_y = float(np.clip(marker_y, clip_bounds[0], clip_bounds[1]))

        marker_size = kwargs.get("markersize", 5.5)
        scatter_kwargs = {
            "color": color,
            "s": marker_size ** 2,
            "zorder": 4,
            "edgecolor": "white",
            "linewidth": kwargs.get("markeredgewidth", 0.6),
        }
        baseline_x = df.loc[baseline_idx, "_x"]
        ax.scatter([baseline_x], [marker_y], **scatter_kwargs)

    return x



def main() -> None:
    args = parse_args()

    if not (0.0 <= args.clip_quantile < 0.5):
        raise SystemExit("--clip-quantile must be in [0, 0.5)")

    main_ols_path = args.ols.resolve()
    df_ols = _ensure_dataframe(main_ols_path, estimator="OLS")
    df_ols, baseline_idx_ols = _prepare(df_ols)

    df_iv: pd.DataFrame | None = None
    baseline_idx_iv: int | None = None
    if args.iv:
        df_iv = _ensure_dataframe(args.iv, estimator="IV")
        df_iv, baseline_idx_iv = _prepare(df_iv)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    ax.set_axisbelow(True)
    style_axes(ax)

    clip_bounds: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    yticks: list[float] | None = None

    if args.ylim:
        ylim = (float(args.ylim[0]), float(args.ylim[1]))
        clip_bounds = ylim
    else:
        source_df = df_iv if args.series == "iv" and df_iv is not None else df_ols
        outcome_name = None
        if "outcome" in source_df.columns and not source_df.empty:
            outcome_name = source_df["outcome"].iloc[0]

        bounds_arrays: list[np.ndarray] = []
        if args.series in {"ols", "both"} and not df_ols.empty:
            bounds_arrays.append(df_ols[["lb", "ub"]].to_numpy(dtype=float))
        if df_iv is not None and args.series in {"iv", "both"} and not df_iv.empty:
            bounds_arrays.append(df_iv[["lb", "ub"]].to_numpy(dtype=float))
        if args.limit_ols:
            for extra in args.limit_ols:
                extra_path = extra.resolve()
                if extra_path == main_ols_path:
                    continue
                arr = _load_ols_bounds(extra_path)
                if arr is not None:
                    bounds_arrays.append(arr)

        if bounds_arrays:
            combined = np.concatenate(bounds_arrays)
            auto_lo, auto_hi = compute_padded_limits(combined)
            if outcome_name in EVENT_YLIMS:
                preset_lo, preset_hi = EVENT_YLIMS[outcome_name]
                auto_lo = max(auto_lo, preset_lo)
                auto_hi = min(auto_hi, preset_hi)
                if auto_lo >= auto_hi:
                    auto_lo, auto_hi = preset_lo, preset_hi
            ylim = (auto_lo, auto_hi)
            clip_bounds = ylim
        elif outcome_name in EVENT_YLIMS:
            ylim = EVENT_YLIMS[outcome_name]
            clip_bounds = ylim

        if outcome_name in EVENT_YTICKS:
            yticks = EVENT_YTICKS[outcome_name]

    plotted_x: np.ndarray | None = None

    if args.series in {"ols", "both"}:
        plotted_x = _plot_series(
            ax,
            df_ols,
            label="OLS" if args.legend_loc.lower() != "none" else "",
            color=SERIES_COLOR,
            clip_bounds=clip_bounds,
            baseline_idx=baseline_idx_ols,
        )

    if df_iv is not None and args.series in {"iv", "both"}:
        plotted_x = _plot_series(
            ax,
            df_iv,
            label="IV" if args.legend_loc.lower() != "none" else "",
            color=CONTROL_COLOR,
            clip_bounds=clip_bounds,
            baseline_idx=baseline_idx_iv,
        )

    if plotted_x is None:
        raise SystemExit("No series plotted: adjust --series / --iv inputs")

    ax.axhline(0.0, color="#2f2f2f", linewidth=1.0, zorder=1)

    boundary_x = None
    candidate_df = df_iv if args.series == "iv" and df_iv is not None else df_ols
    candidate_baseline_idx = baseline_idx_iv if args.series == "iv" and df_iv is not None else baseline_idx_ols
    if candidate_baseline_idx is not None:
        baseline_x = candidate_df.loc[candidate_baseline_idx, "_x"]
        following = candidate_df.loc[candidate_df["_x"] > baseline_x, "_x"]
        next_x = following.min() if not following.empty else None
        if next_x is not None and np.isfinite(next_x):
            boundary_x = baseline_x + (next_x - baseline_x) / 2.0
        else:
            boundary_x = baseline_x + 0.5

    if boundary_x is not None:
        ax.axvline(boundary_x, color="#2f2f2f", linewidth=1.0, linestyle=":", zorder=1)

    if args.title:
        ax.set_title(args.title)
    ax.set_ylabel(args.ylabel, labelpad=18)
    ax.set_xlabel(args.xlabel, labelpad=16)

    source_df = df_iv if args.series == "iv" and df_iv is not None else df_ols
    labels = source_df.get("period_label", source_df.get("yh"))
    if labels is None:
        labels = [str(x) for x in source_df["_x"]]
    else:
        labels = labels.fillna(source_df.get("yh")).tolist()

    ax.set_xticks(source_df["_x"].to_numpy(dtype=float))
    ax.set_xticklabels(labels)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    if ylim:
        ax.set_ylim(ylim)
    if yticks:
        filtered = [t for t in yticks if not np.isnan(t) and ylim and ylim[0] <= t <= ylim[1]]
        if filtered:
            ax.set_yticks(filtered)
        else:
            ax.set_yticks(np.linspace(ylim[0], ylim[1], 5))

    if args.legend_loc and args.legend_loc.lower() != "none":
        ax.legend(loc=args.legend_loc, frameon=False)

    apply_standard_figure_layout(fig)
    fig.savefig(args.output, dpi=FIG_DPI, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
