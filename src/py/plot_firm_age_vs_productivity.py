#!/usr/bin/env python3
"""Plot firm age against productivity residuals for remote-oriented firms."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from project_paths import (
    DATA_PROCESSED,
    RESULTS_CLEANED_FIGURES,
    ensure_dir,
    relative_to_project,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Residualise a productivity measure by individual and time fixed "
            "effects, then scatter firm age against the adjusted outcome with "
            "pre/post-pandemic colouring."
        )
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DATA_PROCESSED / "user_panel_precovid.dta"),
        help="Panel file with user-level productivity (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_CLEANED_FIGURES / "firm_age_vs_productivity_remote.png"),
        help="Destination for the scatter plot (default: %(default)s).",
    )
    parser.add_argument(
        "--value-col",
        type=str,
        default="total_contributions_q100",
        help="Productivity column to residualise (default: %(default)s).",
    )
    parser.add_argument(
        "--entity-col",
        type=str,
        default="user_id",
        help="Column defining the individual fixed effects (default: %(default)s).",
    )
    parser.add_argument(
        "--time-col",
        type=str,
        default="yh",
        help="Column defining the time fixed effects (default: %(default)s).",
    )
    parser.add_argument(
        "--firm-col",
        type=str,
        default="firm_id",
        help="Firm identifier column (default: %(default)s).",
    )
    parser.add_argument(
        "--age-col",
        type=str,
        default="age",
        help="Firm age column in years (default: %(default)s).",
    )
    parser.add_argument(
        "--max-age",
        type=float,
        default=None,
        help="Optional upper bound on firm age before aggregation.",
    )
    parser.add_argument(
        "--remote-col",
        type=str,
        default="remote",
        help="Column capturing remote intensity (default: %(default)s).",
    )
    parser.add_argument(
        "--age-bin-width",
        type=float,
        default=None,
        help="If set, aggregate firm-period means into age bins of this width before plotting.",
    )
    parser.add_argument(
        "--remote-threshold",
        type=float,
        default=0.8,
        help=(
            "Minimum average remote share at the firm level for inclusion "
            "(set negative to disable, default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--min-firm-obs",
        type=int,
        default=25,
        help=(
            "Minimum observation count per firm-period for the plot "
            "(default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--company",
        action="append",
        default=None,
        help="Restrict to specific firm_ids (repeatable).",
    )
    parser.add_argument(
        "--post-indicator",
        type=str,
        default="covid",
        help=(
            "Binary indicator for post-pandemic observations "
            "(1=post, 0=pre; default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Figure resolution in dots per inch (default: %(default)s).",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional title for the figure.",
    )
    return parser.parse_args()


def _two_way_fe_adjusted(
    df: pd.DataFrame,
    value_col: str,
    entity_col: str,
    time_col: str,
    *,
    tol: float = 1e-8,
    max_iter: int = 500,
) -> pd.Series:
    """Return value residualised for entity/time FE, shifted by its mean."""
    work = df[[value_col, entity_col, time_col]].dropna()
    if work.empty:
        raise ValueError("No observations available after dropping NA rows.")

    y = work[value_col].to_numpy(dtype=float)
    entities, entity_idx = np.unique(work[entity_col], return_inverse=True)
    times, time_idx = np.unique(work[time_col], return_inverse=True)
    n_entities = len(entities)
    n_times = len(times)

    y_mean = y.mean()
    alpha = np.zeros(n_entities)
    gamma = np.zeros(n_times)
    counts_e = np.bincount(entity_idx, minlength=n_entities)
    counts_t = np.bincount(time_idx, minlength=n_times)

    for _ in range(max_iter):
        alpha_num = np.bincount(
            entity_idx, weights=y - y_mean - gamma[time_idx], minlength=n_entities
        )
        new_alpha = np.zeros_like(alpha)
        valid_e = counts_e > 0
        new_alpha[valid_e] = alpha_num[valid_e] / counts_e[valid_e]

        gamma_num = np.bincount(
            time_idx, weights=y - y_mean - new_alpha[entity_idx], minlength=n_times
        )
        new_gamma = np.zeros_like(gamma)
        valid_t = counts_t > 0
        new_gamma[valid_t] = gamma_num[valid_t] / counts_t[valid_t]

        delta = 0.0
        if valid_e.any():
            delta = max(delta, np.abs(new_alpha[valid_e] - alpha[valid_e]).max())
        if valid_t.any():
            delta = max(delta, np.abs(new_gamma[valid_t] - gamma[valid_t]).max())

        alpha, gamma = new_alpha, new_gamma
        if delta < tol:
            break

    adjusted = y - y_mean - alpha[entity_idx] - gamma[time_idx] + y_mean
    series = pd.Series(adjusted, index=work.index, name=f"{value_col}_fe_adj")
    return series


def load_panel(path: str | Path, columns: Iterable[str]) -> pd.DataFrame:
    path = relative_to_project(path)
    if path.suffix.lower() == ".dta":
        return pd.read_stata(path, columns=list(columns))
    return pd.read_csv(path, usecols=list(columns))


def main() -> None:
    args = parse_args()

    required_cols = {
        args.value_col,
        args.entity_col,
        args.time_col,
        args.firm_col,
        args.age_col,
        args.remote_col,
        args.post_indicator,
    }
    panel = load_panel(args.input, required_cols)

    if args.company:
        panel = panel[panel[args.firm_col].isin(args.company)]

    # Drop rows lacking core inputs before fixed-effect adjustment.
    panel = panel.dropna(subset=[args.value_col, args.entity_col, args.time_col])
    if panel.empty:
        raise ValueError("All observations dropped before residualisation.")

    adjusted = _two_way_fe_adjusted(
        panel, args.value_col, args.entity_col, args.time_col
    )
    panel = panel.join(adjusted)

    # Compute firm-level remote intensity and filter if requested.
    firm_remote = (
        panel.groupby(args.firm_col, observed=True)[args.remote_col]
        .mean()
        .rename("remote_share")
    )
    panel = panel.join(firm_remote, on=args.firm_col)
    if args.remote_threshold >= 0:
        keep = firm_remote[firm_remote >= args.remote_threshold].index
        panel = panel[panel[args.firm_col].isin(keep)]

    if args.max_age is not None:
        panel = panel[panel[args.age_col] <= args.max_age]

    panel = panel.dropna(subset=[f"{args.value_col}_fe_adj", args.age_col])
    if panel.empty:
        raise ValueError("No observations left after remote and age filtering.")

    panel["period"] = np.where(panel[args.post_indicator].astype(int) == 1, "Post", "Pre")

    agg = (
        panel.groupby([args.firm_col, "period"], observed=True)
        .agg(
            {
                args.age_col: "mean",
                f"{args.value_col}_fe_adj": "mean",
                args.remote_col: "mean",
                args.value_col: "count",
                "remote_share": "mean",
            }
        )
        .rename(columns={args.value_col: "n_obs"})
        .reset_index()
    )
    agg = agg[agg["n_obs"] >= args.min_firm_obs]
    if agg.empty:
        raise ValueError("Filtered aggregation is empty; relax constraints.")

    output_path = ensure_dir(Path(args.output).resolve().parent) / Path(args.output).name

    fig, ax = plt.subplots(figsize=(7.5, 5))
    periods = agg["period"].unique()

    trend_data: dict[str, pd.DataFrame] = {}
    shape_entries: list[tuple[str, str]] = []
    colorbar_ref = None
    if args.age_bin_width:
        width = args.age_bin_width
        if width <= 0:
            raise ValueError("age-bin-width must be positive.")
        upper = np.ceil(agg[args.age_col].max() / width) * width
        bins = np.arange(0, upper + width, width)
        if bins.size < 2:
            bins = np.array([0, upper + width])
        agg["age_bin"] = pd.cut(
            agg[args.age_col], bins=bins, include_lowest=True, right=False
        )
        bin_summary = (
            agg.groupby(["age_bin", "period"], observed=True)
            .agg(
                age_mid=(args.age_col, "mean"),
                outcome=(f"{args.value_col}_fe_adj", "mean"),
                remote_mean=("remote_share", "mean"),
                weight=("n_obs", "sum"),
            )
            .dropna(subset=["age_mid"])
            .reset_index()
        )
        markers = {"Pre": "o", "Post": "s"}
        scatter_handles = []
        for period in periods:
            mask = bin_summary["period"] == period
            if not mask.any():
                continue
            sc = ax.scatter(
                bin_summary.loc[mask, "age_mid"],
                bin_summary.loc[mask, "outcome"],
                c=bin_summary.loc[mask, "remote_mean"],
                cmap="viridis",
                alpha=0.9,
                s=np.clip(bin_summary.loc[mask, "weight"] * 1.5, 40, 400),
                marker=markers.get(period, "o"),
                edgecolor="black",
                linewidths=0.4,
            )
            scatter_handles.append(sc)
            if colorbar_ref is None:
                colorbar_ref = sc
            shape_entries.append((markers.get(period, "o"), f"{period} (bins={mask.sum()})"))
            trend_data[period] = bin_summary.loc[mask, ["age_mid", "outcome"]].dropna()
        scatter = scatter_handles[0] if scatter_handles else ax.scatter([], [])
    else:
        markers = {"Pre": "o", "Post": "s"}
        scatter = None
        for period in periods:
            mask = agg["period"] == period
            if mask.any():
                sc = ax.scatter(
                    agg.loc[mask, args.age_col],
                    agg.loc[mask, f"{args.value_col}_fe_adj"],
                    c=agg.loc[mask, "remote_share"],
                    cmap="viridis",
                    alpha=0.8,
                    s=30,
                    marker=markers.get(period, "o"),
                    edgecolor="black",
                    linewidths=0.4,
                )
                if colorbar_ref is None:
                    colorbar_ref = sc
                if scatter is None:
                    scatter = sc
                shape_entries.append(
                    (markers.get(period, "o"), f"{period} (n={mask.sum()})")
                )
                trend_data[period] = agg.loc[
                    mask, [args.age_col, f"{args.value_col}_fe_adj"]
                ].dropna()
        if scatter is None:
            scatter = ax.scatter([], [])

    if colorbar_ref is not None:
        cbar = fig.colorbar(colorbar_ref, ax=ax)
        cbar.set_label("Average remote share")

    line_handles = []
    for period, data in trend_data.items():
        if len(data) < 2:
            continue
        x = data.iloc[:, 0].to_numpy()
        y = data.iloc[:, 1].to_numpy()
        coeff = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 100)
        y_line = np.polyval(coeff, x_line)
        color = "#1f77b4" if period == "Pre" else "#d62728"
        handle = ax.plot(
            x_line,
            y_line,
            linestyle="--",
            linewidth=1.0,
            color=color,
            alpha=0.6,
        )[0]
        handle.set_label(f"{period} trend")
        line_handles.append((period, handle))

    shape_handles = [
        Line2D(
            [],
            [],
            marker=marker,
            linestyle="",
            markerfacecolor="white",
            markeredgecolor="black",
            markersize=8,
            label=label,
        )
        for marker, label in shape_entries
    ]
    handles = shape_handles + [handle for _, handle in line_handles]
    labels = [h.get_label() for h in shape_handles] + [
        f"{period} trend" for period, _ in line_handles
    ]
    if handles:
        ax.legend(handles, labels, frameon=False, loc="best")
    ax.set_xlabel("Firm age (years)")
    ax.set_ylabel(f"{args.value_col} (FE residual + mean)")
    title = args.title if args.title else "Firm age vs. productivity residuals"
    ax.set_title(title)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=args.dpi)
    print(f"✓ Figure saved to {output_path}")


if __name__ == "__main__":
    main()
