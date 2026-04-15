"""Shared Matplotlib styling helpers for project figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

FONT_FAMILY = "Palatino"
TITLE_SIZE = 18.2
AXIS_LABEL_SIZE = 15.6
TICK_LABEL_SIZE = 13
AXIS_COLOR = "#2f2f2f"
GRID_COLOR = "#d9d9d9"
LINEWIDTH = 1.8
FIGSIZE = (8, 5)
FIG_DPI = 300

SERIES_COLOR = "#111111"
CONTROL_COLOR = "#666666"
SECONDARY_COLOR = "#d04e23"
ERROR_COLOR = "#b0b0b0"

# Palette for multi-series IRF plots (cycled when more than two roles are shown)
ROLE_COLOR_CYCLE = [
    "#111111",  # dark grey/black
    "#d04e23",  # vermilion
    "#1f78b4",  # blue
    "#33a02c",  # green
    "#6a3d9a",  # purple
    "#ff7f00",  # orange
    "#b15928",  # brown
]

# Convenience mapping for common RHS labels used in IRF scripts
IRF_SERIES_COLORS = {
    "Engineer": SERIES_COLOR,
    "NonEngineer": SECONDARY_COLOR,
    "Technical": SERIES_COLOR,
    "NonTechnical": SECONDARY_COLOR,
}

EVENT_YLIMS = {
    'total_contributions_q100': (-10, 10),
    'growth_rate_we': (-0.3, 0.3),
    'join_rate_we': (-0.3, 0.3),
    'leave_rate_we': (-0.3, 0.3),
    'vacancies_thousands': (-2.0, 4.5),
    'hires_to_vacancies_winsor': (-5.0, 5.0),
}

EVENT_YTICKS = {
    'growth_rate_we': [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3],
    'join_rate_we': [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3],
    'leave_rate_we': [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3],
}

IRF_YLIMS = {
    ('remote1', 'Engineer'): (-1.5, 5.0),
    ('hybrid', 'Engineer'): (-2.5, 10.0),
}
IRF_PRESET_LIMITS = IRF_YLIMS  # backwards-compatible alias
STANDARD_FIGURE_MARGINS = dict(left=0.12, right=0.98, top=0.92, bottom=0.15)


def apply_mpl_defaults() -> None:
    """Set global Matplotlib defaults used across plotting scripts."""
    plt.rcParams.update({
        'font.family': FONT_FAMILY,
        'axes.titlesize': TITLE_SIZE,
        'axes.labelsize': AXIS_LABEL_SIZE,
        'xtick.labelsize': TICK_LABEL_SIZE,
        'ytick.labelsize': TICK_LABEL_SIZE,
        'legend.fontsize': TICK_LABEL_SIZE,
        'axes.edgecolor': AXIS_COLOR,
        'axes.linewidth': 0.9,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'lines.linewidth': LINEWIDTH,
    })


def style_axes(ax: plt.Axes, *, ygrid: bool = True) -> None:
    """Apply shared axis styling."""
    ax.set_facecolor('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color(AXIS_COLOR)
        ax.spines[spine].set_linewidth(1.0)
    ax.tick_params(colors=AXIS_COLOR, labelsize=TICK_LABEL_SIZE, width=0.8, length=5)
    if ygrid:
        ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.6)
    else:
        ax.yaxis.grid(False)
    ax.xaxis.grid(False)


def set_integer_xticks(ax: plt.Axes, values: np.ndarray) -> None:
    """Set integer ticks spanning the provided horizon values."""
    ticks = np.unique(np.asarray(values))
    ticks = np.asarray(sorted(ticks))
    ax.set_xticks(ticks)
    if ticks.size:
        ax.set_xlim(ticks[0] - 0.1, ticks[-1] + 0.1)


def errorbar_kwargs(color: str) -> dict[str, float | str]:
    """Standardised kwargs for errorbar markers."""
    return {
        'fmt': '-o',
        'color': color,
        'ecolor': ERROR_COLOR,
        'elinewidth': 1.2,
        'capsize': 4,
        'markersize': 5.5,
        'markeredgecolor': 'white',
        'markeredgewidth': 0.6,
    }


def get_series_color(label: str, *, default: str | None = None, index: int | None = None) -> str:
    """
    Return a colour for a named IRF series.

    Parameters
    ----------
    label:
        RHS/role label (e.g. "Engineer", "Sales").
    default:
        Fallback colour when ``label`` is unknown.
    index:
        Optional index into the role colour cycle when ``label`` is not found.
    """
    if label in IRF_SERIES_COLORS:
        return IRF_SERIES_COLORS[label]
    if index is not None:
        return ROLE_COLOR_CYCLE[index % len(ROLE_COLOR_CYCLE)]
    if default is not None:
        return default
    return ROLE_COLOR_CYCLE[0]


def compute_padded_limits(
    values,
    *,
    pad_ratio: float = 0.08,
    min_span: float = 0.05,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
) -> tuple[float, float]:
    """
    Compute axis limits that tightly envelope ``values`` with a small padding.

    Parameters
    ----------
    values:
        Iterable of numeric values (arrays/pandas/series accepted).
    pad_ratio:
        Fraction of the observed span used as symmetric padding.
    min_span:
        Minimum span enforced when values are (nearly) constant.
    lower_bound, upper_bound:
        Optional hard bounds to clip the resulting limits.
    """
    arr = np.asarray(values, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return (-0.1, 0.1)

    lo = float(np.min(arr))
    hi = float(np.max(arr))
    span = max(hi - lo, min_span)
    pad = max(span * pad_ratio, min_span * 0.25)
    lo -= pad
    hi += pad

    if lower_bound is not None:
        lo = max(lo, lower_bound)
    if upper_bound is not None:
        hi = min(hi, upper_bound)
    if lo >= hi:
        hi = lo + min_span
    return lo, hi


def compute_irf_limits(
    *,
    center=None,
    lower=None,
    upper=None,
    preset_key: tuple[str, str] | str | None = None,
    fallback: tuple[float, float] = (-0.2, 0.2),
    pad_ratio: float = 0.08,
) -> tuple[float, float]:
    """
    Compute category-aware IRF limits using confidence bands and presets.

    Parameters
    ----------
    center, lower, upper:
        Iterables containing the point estimates and confidence band bounds.
        Any subset can be supplied; provided arrays are combined when computing
        the padded limits.
    preset_key:
        Optional key (tuple or string) used to look up hard limits in
        ``IRF_YLIMS`` / ``IRF_PRESET_LIMITS``.
    fallback:
        Returned when no numeric data are supplied.
    pad_ratio:
        Passed through to :func:`compute_padded_limits`.
    """
    arrays = []
    for arr in (center, lower, upper):
        if arr is None:
            continue
        vals = np.asarray(arr, dtype=float).ravel()
        vals = vals[np.isfinite(vals)]
        if vals.size:
            arrays.append(vals)

    if not arrays:
        return fallback

    combined = np.concatenate(arrays)
    lo, hi = compute_padded_limits(combined, pad_ratio=pad_ratio, min_span=fallback[1] - fallback[0])

    if preset_key is not None and preset_key in IRF_PRESET_LIMITS:
        preset_lo, preset_hi = IRF_PRESET_LIMITS[preset_key]
        lo = max(lo, preset_lo)
        hi = min(hi, preset_hi)
        if lo >= hi:
            lo, hi = preset_lo, preset_hi

    return lo, hi


def apply_standard_figure_layout(fig: plt.Figure) -> None:
    """Apply consistent subplot margins to align axes across figures."""
    fig.subplots_adjust(**STANDARD_FIGURE_MARGINS)
