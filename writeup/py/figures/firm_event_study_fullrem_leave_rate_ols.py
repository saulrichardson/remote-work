#!/usr/bin/env python3
"""Build the active full-remote firm leave-rate event-study figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from writeup.py.plot_style import EVENT_YLIMS, EVENT_YTICKS, FIGSIZE, FIG_DPI, SERIES_COLOR, apply_mpl_defaults, apply_standard_figure_layout, errorbar_kwargs, style_axes, compute_padded_limits
from src.py.project_paths import RESULTS_RAW, RESULTS_CLEANED_FIGURES, ensure_dir

apply_mpl_defaults()
INPUT = RESULTS_RAW / "12_firm_event_study_fullrem_leave_rate_ols" / "ols_leave_rate_we.csv"
OUTPUT = RESULTS_CLEANED_FIGURES / "firm_event_study_fullrem_leave_rate_ols.png"
YLABEL = "Change in leave rate"


def _prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, int | None]:
    order = [col for col in ("event_time", "period", "yh") if col in df.columns]
    df = df.sort_values(order).reset_index(drop=True) if order else df.reset_index(drop=True)
    for col in ("b", "lb", "ub"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "event_time" in df.columns:
        df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
        df["_x"] = df["event_time"].to_numpy(dtype=float)
    else:
        df["_x"] = np.arange(len(df), dtype=float)
    omitted = df.get("omitted", False)
    omitted = omitted.astype(bool) if isinstance(omitted, pd.Series) else pd.Series(False, index=df.index)
    idxs = df.index[omitted].tolist()
    baseline = idxs[0] if idxs else None
    if baseline is not None:
        df.loc[baseline, ["b", "lb", "ub"]] = np.nan
    return df, baseline


def _plot(ax: plt.Axes, df: pd.DataFrame, baseline: int | None, ylim: tuple[float, float]) -> None:
    y = np.clip(df["b"].to_numpy(dtype=float), ylim[0], ylim[1])
    lower = np.clip(df["lb"].to_numpy(dtype=float), ylim[0], ylim[1])
    upper = np.clip(df["ub"].to_numpy(dtype=float), ylim[0], ylim[1])
    err = np.vstack((y - lower, upper - y))
    err = np.nan_to_num(err, nan=0.0)
    err[err < 0.0] = 0.0
    x = df["_x"].to_numpy(dtype=float)
    kwargs = errorbar_kwargs(SERIES_COLOR).copy()
    kwargs["fmt"] = "o"
    ax.errorbar(x, y, yerr=err, **kwargs)
    if baseline is not None:
        ax.scatter([df.loc[baseline, "_x"]], [0.0], color=SERIES_COLOR, s=kwargs.get("markersize", 5.5) ** 2, zorder=4, edgecolor="white", linewidth=kwargs.get("markeredgewidth", 0.6))


def main() -> None:
    df = pd.read_csv(INPUT)
    if "estimator" in df.columns:
        df = df[df["estimator"].str.upper() == "OLS"].copy()
    df, baseline = _prepare(df)
    outcome = df["outcome"].iloc[0] if "outcome" in df.columns and not df.empty else None
    ylim = EVENT_YLIMS.get(outcome, compute_padded_limits(df[["lb", "ub"]].to_numpy(dtype=float)))
    yticks = EVENT_YTICKS.get(outcome)
    ensure_dir(OUTPUT.parent)
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    ax.set_axisbelow(True)
    style_axes(ax)
    _plot(ax, df, baseline, ylim)
    ax.axhline(0.0, color="#2f2f2f", linewidth=1.0, zorder=1)
    if baseline is not None:
        bx = df.loc[baseline, "_x"]
        nxt = df.loc[df["_x"] > bx, "_x"]
        nx = nxt.min() if not nxt.empty else None
        ax.axvline(bx + (nx - bx) / 2.0 if nx is not None and np.isfinite(nx) else bx + 0.5, color="#2f2f2f", linewidth=1.0, linestyle=":", zorder=1)
    labels = df.get("period_label", df.get("yh"))
    labels = labels.fillna(df.get("yh")).tolist() if labels is not None else [str(x) for x in df["_x"]]
    ax.set_xticks(df["_x"].to_numpy(dtype=float))
    ax.set_xticklabels(labels)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_ylabel(YLABEL, labelpad=18)
    ax.set_xlabel("Event time", labelpad=16)
    ax.set_ylim(ylim)
    if yticks:
        flt = [t for t in yticks if not np.isnan(t) and ylim[0] <= t <= ylim[1]]
        ax.set_yticks(flt if flt else np.linspace(ylim[0], ylim[1], 5))
    apply_standard_figure_layout(fig)
    fig.savefig(OUTPUT, dpi=FIG_DPI, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()

