#!/usr/bin/env python3
from __future__ import annotations

"""make_core_figures.py

Generates **firm‑level** binscatter figures for the project.  All plots use
*quantile (equal‑frequency) bins* (Stata‑style `binscatter`) and are written to
`results/cleaned/figures/`.

Relationships visualised
------------------------
1. **Firm age → remoteness score**  (full sample, age < 50, log‑age)
2. **Teleworkable index → remoteness score**  (single view, **no raw‑scatter backdrop**)
3. **Firm age → post‑COVID growth rate**, split remote vs non‑remote  (full, <50, log‑age)
4. **Firm age → post‑COVID productivity**  (mean worker Q100), split remote vs non‑remote  (full, <50, log‑age)

Inputs (CSV expected under `data/samples/`)
------------------------------------------
* `firm_panel.csv`   – must contain  
  `firm_id`, `age` (years since founding), `remote`, `teleworkable`,
  `growth_rate_we`, `covid`.
* `user_panel_<variant>.csv` – must contain (e.g. `user_panel_unbalanced.csv`)
  `firm_id`, `covid`, `total_contributions_q100`.
"""

import argparse
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

try:
    from binsreg import binsreg
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        "binsreg is not installed. Run `pip install binsreg` inside the project virtualenv "
        "before executing src/py/figures.py."
    ) from exc

from plot_style import (
    FIGSIZE,
    FIG_DPI,
    apply_standard_figure_layout,
    compute_padded_limits,
)
from project_paths import DATA_SAMPLES, RESULTS_CLEANED_FIGURES, ensure_dir

# Shared plotting style ------------------------------------------------------
plt.rcParams.update({
    'font.family': 'Palatino',
    'axes.titlesize': 18.2,
    'axes.labelsize': 15.6,
    'axes.edgecolor': '#4a4a4a',
    'axes.linewidth': 0.8,
    'xtick.color': '#4a4a4a',
    'ytick.color': '#4a4a4a',
})

DATA_DIR = DATA_SAMPLES
OUTPUT_DIR = ensure_dir(RESULTS_CLEANED_FIGURES)


def _read_csv_flexible(path: Path) -> pd.DataFrame:
    """Read CSV with UTF-8, falling back to latin-1 for legacy bytes."""
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")

# 3) File paths
WORKER_FILE = DATA_DIR / "user_panel_precovid.csv"
FIRM_FILE = DATA_DIR / "firm_panel.csv"

###############################################################################
# CONSTANTS
###############################################################################
REMOTE_THRESHOLD = 0.5          # firm considered remote if remote_score > 0.5
FIRM_N_BINS      = 60           # quantile bins in all firm‑level charts
COLOURS          = {True: '#111111', False: '#444444'}

###############################################################################
# HELPER FUNCTIONS
###############################################################################

def _quantile_bins(df: pd.DataFrame, x: str, y: str, q: int) -> tuple[np.ndarray, np.ndarray]:
    """Fallback: equal-frequency bins via pandas.qcut."""
    tmp = df[[x, y]].dropna().copy()
    if tmp.empty:
        raise ValueError("No observations left after filtering NaNs")
    tmp["bin"] = pd.qcut(tmp[x], q=min(q, tmp[x].nunique()), duplicates="drop")
    grouped = tmp.groupby("bin", observed=False)[[x, y]].mean()
    return grouped[x].to_numpy(), grouped[y].to_numpy()


def _binsreg_points(
    df: pd.DataFrame,
    x: str,
    y: str,
    nbins: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return within-bin x/fit pairs using binsreg with graceful fallbacks."""

    df_valid = df[[x, y]].dropna()
    if df_valid.empty or df_valid[x].nunique() < 2:
        raise ValueError("Insufficient variation for binsreg")

    unique_x = df_valid[x].nunique()
    candidate_bins = []
    if unique_x > 2:
        candidate_bins.append(min(nbins, unique_x - 1))
    candidate_bins.append(max(2, min(20, unique_x - 1)))
    candidate_bins = [b for b in candidate_bins if b >= 2]

    def run_binsreg(nbins_override: int | None):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            return binsreg(
                df_valid[y].to_numpy(),
                df_valid[x].to_numpy(),
                nbins=nbins_override,
                noplot=True,
                nsims=0,
                binsmethod="dpi",
                binspos="qs",
            )

    tries = [None] + candidate_bins
    for nbins_override in tries:
        try:
            res = run_binsreg(nbins_override)
        except Exception:
            continue
        dots = res.data_plot[0].dots if res.data_plot else None
        if dots is not None and not dots.empty:
            return dots["x"].to_numpy(), dots["fit"].to_numpy()

    # Fallback to quantile bins if binsreg never produced dots
    return _quantile_bins(df_valid, x, y, nbins)



def _style_axes(ax):
    ax.set_facecolor('white')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color('#3a3a3a')
        ax.spines[spine].set_linewidth(0.9)
    ax.tick_params(colors='#3a3a3a', labelsize=13, width=0.8)
    ax.yaxis.grid(True, color='#d0d0d0', linewidth=0.6)
    ax.xaxis.grid(False)


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
    """Quantile‑binscatter with optional remote split and OLS overlay."""
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    _style_axes(ax)

    groups = data.groupby(split_col) if split_col else [("All", data)]
    for key, grp in groups:
        # skip groups with insufficient data points or variation
        grp_valid = grp.dropna(subset=[x, y])
        if len(grp_valid) < 3 or grp_valid[x].nunique() < 2:
            continue
        # adjust requested bins for the available support
        group_q = max(2, min(q, grp_valid[x].nunique() - 1))
        colour = COLOURS.get(key, "black")
        try:
            xs, ys = _binsreg_points(grp_valid, x, y, group_q)
        except ValueError:
            continue
        label_bs = (
            f"{'Remote' if key else 'Non‑remote'} (Binscatter)"
            if split_col else "Binscatter"
        )
        plt.plot(xs, ys, "o", linewidth=2.2, color=colour, label=label_bs, markeredgecolor='white', markeredgewidth=0.5)

        model  = smf.ols(f"{y} ~ {x}", data=grp_valid).fit()
        slope = model.params[x]
        r2    = model.rsquared
        x_vals = np.linspace(grp_valid[x].min(), grp_valid[x].max(), 100)
        y_vals = model.predict(pd.DataFrame({x: x_vals}))
        label_ols = (
            f"{'Remote' if key else 'Non‑remote'} (OLS)"
            if split_col else "OLS"
        )
        plt.plot(x_vals, y_vals, linewidth=2.2, color=colour, label=label_ols)

        if x == "teleworkable" and y == "remote":
            slope = model.params[x]
            se    = model.bse[x]
            r2    = model.rsquared
            anno_text = (
                rf"$\beta = {slope:.2f}\;({se:.2f})$" "\n"
                rf"$R^2 = {r2:.2f}$"
            )
            ax.text(
                0.05,
                0.95,
                anno_text,
                transform=ax.transAxes,
                fontsize=11,
                verticalalignment="top",
                horizontalalignment="left",
                color=colour,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.6, edgecolor=colour),
            )

        # Annotate β and R² for age → remote plots (full sample, no split)
        elif x in {"age", "log_age"} and y == "remote" and split_col is None:
            slope = model.params[x]
            se    = model.bse[x]
            r2    = model.rsquared

            anno_text = (
                rf"$\beta = {slope:.2f}\;({se:.2f})$" "\n"
                rf"$R^2 = {r2:.2f}$"
            )

            # Place annotation in top-right corner
            ax.text(
                0.95,
                0.95,
                anno_text,
                transform=ax.transAxes,
                fontsize=11,
                verticalalignment="top",
                horizontalalignment="right",
                color=colour,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.6, edgecolor=colour),
            )

            if split_col is None:
                # pick corner with fewest nearby points
                x_mid, y_mid = grp_valid[x].median(), grp_valid[y].median()
                counts = {
                    "tl": ((grp_valid[x] < x_mid) & (grp_valid[y] > y_mid)).sum(),
                    "tr": ((grp_valid[x] > x_mid) & (grp_valid[y] > y_mid)).sum(),
                    "bl": ((grp_valid[x] < x_mid) & (grp_valid[y] < y_mid)).sum(),
                    "br": ((grp_valid[x] > x_mid) & (grp_valid[y] < y_mid)).sum(),
                }
                corner = min(counts, key=counts.get)
                corners = {
                    "tl": (0.95, 0.95, "right", "top"),
                    "tr": (0.95, 0.95, "right", "top"),
                    "bl": (0.95, 0.05, "right", "bottom"),
                    "br": (0.95, 0.05, "right", "bottom"),
                }
                base_x, base_y, ha, va = corners[corner]
            else:
                base_x, base_y = 0.05, 0.90
                if key:
                    base_y -= 0.10
                ha, va = "left", "top"

            ax.text(
                base_x,
                base_y,
                anno_text,
                transform=ax.transAxes,
                fontsize=11,
                horizontalalignment=ha,
                verticalalignment=va,
                color=colour,
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    alpha=0.6,
                    edgecolor=colour,
                ),
            )
            if key in (None, True):
                # duplicated label for remote series anchored top-left
                ax.text(
                    0.05,
                    0.95,
                    anno_text,
                    transform=ax.transAxes,
                    fontsize=11,
                    horizontalalignment="left",
                    verticalalignment="top",
                    color=colour,
                    bbox=dict(
                        boxstyle="round,pad=0.3",
                        facecolor="white",
                        alpha=0.6,
                        edgecolor=colour,
                    ),
                )


    ax.tick_params(axis="both", labelsize=12)
    plt.xlabel(xlabel, fontsize=14)
    plt.ylabel(ylabel, fontsize=14)
    limits = y_limits if y_limits is not None else compute_padded_limits(data[y].dropna())
    ax.set_ylim(*limits)
    apply_standard_figure_layout(fig)
    fig.savefig(
        OUTPUT_DIR / f"{file_stem}.png",
        dpi=FIG_DPI,
        facecolor="white",
    )
    plt.close(fig)

###############################################################################
# MAIN WORKFLOW
###############################################################################

def main(worker_file: Path = WORKER_FILE):
    # ────────────────────────── READ DATA ────────────────────────────
    firms   = _read_csv_flexible(FIRM_FILE)
    # keep a single observation per firm (sorted by yh) for remoteness plots
    firms_unique = firms.sort_values("yh").drop_duplicates("firm_id")
    # later growth/productivity figures use the full `firms` DataFrame
    workers = _read_csv_flexible(worker_file)

    # ────────────────── BUILD FIRM‑LEVEL PRODUCTIVITY ────────────────
    prod = (
        workers[workers["covid"] == 1]
        .groupby("firm_id", observed=False)["total_contributions_q100"]
        .mean()
        .rename("q100")
    )
    firms = firms.merge(prod, on="firm_id", how="left")

    # remote indicator used in several plots, preserve missingness
    firms["is_remote"] = np.where(
        firms["remote"].isna(),
        np.nan,
        firms["remote"] > REMOTE_THRESHOLD
    )

    remote_limits = compute_padded_limits(
        firms_unique["remote"].dropna(),
        pad_ratio=0.05,
        min_span=0.05,
        lower_bound=0.0,
        upper_bound=1.0,
    )

    # ───────── 1) Firm age → Remoteness (3 variants, unique firms) ─────────
    # full sample age-based plot (all ages)
    _plot_bins_reg(
        firms_unique,
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Remoteness score",
        file_stem="firm_age_remote_full",
        y_limits=remote_limits,
    )
    # apply age < 100 cutoff for age-based plots
    _plot_bins_reg(
        firms_unique[firms_unique["age"] < 100],
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age", ylabel="Remoteness score",
        file_stem="firm_age_lt100_remote",
        y_limits=remote_limits,
    )

    _plot_bins_reg(
        firms_unique[firms_unique["age"] < 50],
        x="age", y="remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Remoteness score",
        file_stem="firm_age_lt50_remote",
        y_limits=remote_limits,
    )

    # log-age plot: drop non-positive and extreme ages before logging
    firms_log = firms_unique[(firms_unique["age"] > 0) & (firms_unique["age"] < 100)].copy()
    firms_log["log_age"] = np.log(firms_log["age"])
    _plot_bins_reg(
        firms_log,
        x="log_age", y="remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Remoteness score",
        file_stem="firm_logage_remote",
        y_limits=remote_limits,
    )

    # ───────── 2) Teleworkable → Remoteness (single view, no raw scatter)
    #           (using the deduplicated firm set) ─────────
    _plot_bins_reg(
        firms_unique,
        x="teleworkable", y="remote", q=FIRM_N_BINS,
        xlabel="Teleworkable index", ylabel="Remoteness score",
        file_stem="firm_teleworkable_remote",
        y_limits=remote_limits,
    )

"""
    # ───────── 3) Firm age → Growth rate (post‑COVID, split) ─────────
    post = firms[firms["covid"] == 1].copy()
    # full sample post-COVID age-based growth plot (all ages)
    _plot_bins_reg(
        post, x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Growth rate (WE)",
        file_stem="firm_age_growth_full",
    )
    # apply age < 100 cutoff to post-COVID age-based growth plots
    _plot_bins_reg(
        post[post["age"] < 100], x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Growth rate (WE)",
        file_stem="firm_age_lt100_growth",
    )

    _plot_bins_reg(
        post[post["age"] < 50], x="age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Growth rate (WE)",
        file_stem="firm_age_lt50_growth",
    )

    # log-age plot for growth: drop non-positive ages before logging
    post_log = post[post["age"] > 0].copy()
    post_log["log_age"] = np.log(post_log["age"])
    _plot_bins_reg(
        post_log, x="log_age", y="growth_rate_we", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Growth rate (WE)",
        file_stem="firm_logage_growth",
    )

    # ───────── 4) Firm age → Productivity (mean Q100, post‑COVID, split) ─────────
    prod_df = firms[firms["q100"].notna()].copy()  # firms with at least one worker obs post‑COVID
    # full sample post-COVID age-based productivity plot (all ages)
    _plot_bins_reg(
        prod_df, x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (years since founding)", ylabel="Mean worker Q100 (post-COVID)",
        file_stem="firm_age_q100_full",
    )
    # apply age < 100 cutoff to productivity age-based plots
    _plot_bins_reg(
        prod_df[prod_df["age"] < 100], x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<100 years)", ylabel="Mean worker Q100 (post-COVID)",
        file_stem="firm_age_lt100_q100",
    )

    _plot_bins_reg(
        prod_df[prod_df["age"] < 50], x="age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="Firm age (<50 years)", ylabel="Mean worker Q100 (post‑COVID)",
        file_stem="firm_age_lt50_q100",
    )

    # log-age plot for productivity: drop non-positive ages before logging
    prod_log = prod_df[prod_df["age"] > 0].copy()
    prod_log["log_age"] = np.log(prod_log["age"])
    _plot_bins_reg(
        prod_log, x="log_age", y="q100", split_col="is_remote", q=FIRM_N_BINS,
        xlabel="log(Firm age)", ylabel="Mean worker Q100 (post-COVID)",
        file_stem="firm_logage_q100",
    )

"""
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create main figures")
    parser.add_argument(
        "--worker-file",
        type=Path,
        default=WORKER_FILE,
        help="CSV file with worker-level sample",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(worker_file=args.worker_file)
