#!/usr/bin/env python3
"""Build the active core figure for firm age under 100 versus remoteness."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

try:
    from binsreg import binsreg
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "binsreg is not installed. Run `pip install binsreg` inside the project virtualenv "
        "before executing the active core-figure builder."
    ) from exc

from writeup.py.plot_style import FIGSIZE, FIG_DPI, apply_standard_figure_layout, compute_padded_limits
from src.py.project_paths import DATA_CLEAN, RESULTS_CLEANED_FIGURES, ensure_dir, require_file

plt.rcParams.update({
    'font.family': 'Palatino',
    'axes.titlesize': 18.2,
    'axes.labelsize': 15.6,
    'axes.edgecolor': '#4a4a4a',
    'axes.linewidth': 0.8,
    'xtick.color': '#4a4a4a',
    'ytick.color': '#4a4a4a',
})

REMOTE_THRESHOLD = 0.5
FIRM_N_BINS = 60
WORKER_FILE = DATA_CLEAN / "user_panel_precovid.dta"
FIRM_FILE = DATA_CLEAN / "firm_panel.dta"
OUTPUT = RESULTS_CLEANED_FIGURES / "firm_age_lt100_remote.png"


def _read_dataset(path: Path) -> pd.DataFrame:
    require_file(path, nonempty=True, purpose="paper figure input")
    if path.suffix.lower() == ".dta":
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UnicodeWarning)
            return pd.read_stata(path, convert_categoricals=False)
    if path.suffix.lower() == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")
    raise ValueError(f"Unsupported dataset type for {path}")


def _require_columns(df: pd.DataFrame, required: set[str], *, label: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing columns in {label}: {missing}")


def _quantile_bins(df: pd.DataFrame, x: str, y: str, q: int) -> tuple[np.ndarray, np.ndarray]:
    tmp = df[[x, y]].dropna().copy()
    if tmp.empty:
        raise ValueError("No observations left after filtering NaNs")
    tmp["bin"] = pd.qcut(tmp[x], q=min(q, tmp[x].nunique()), duplicates="drop")
    grouped = tmp.groupby("bin", observed=False)[[x, y]].mean()
    return grouped[x].to_numpy(), grouped[y].to_numpy()


def _binsreg_points(df: pd.DataFrame, x: str, y: str, nbins: int) -> tuple[np.ndarray, np.ndarray]:
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

    for nbins_override in [None] + candidate_bins:
        try:
            res = run_binsreg(nbins_override)
        except Exception:
            continue
        dots = res.data_plot[0].dots if res.data_plot else None
        if dots is not None and not dots.empty:
            return dots["x"].to_numpy(), dots["fit"].to_numpy()

    return _quantile_bins(df_valid, x, y, nbins)


def _style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor('white')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    for spine in ('left', 'bottom'):
        ax.spines[spine].set_color('#3a3a3a')
        ax.spines[spine].set_linewidth(0.9)
    ax.tick_params(colors='#3a3a3a', labelsize=13, width=0.8)
    ax.yaxis.grid(True, color='#d0d0d0', linewidth=0.6)
    ax.xaxis.grid(False)


def _load_inputs() -> tuple[pd.DataFrame, tuple[float, float]]:
    firms = _read_dataset(FIRM_FILE)
    _require_columns(firms, {"firm_id", "yh", "age", "remote", "teleworkable", "covid"}, label=str(FIRM_FILE))
    firms_unique = firms.sort_values("yh").drop_duplicates("firm_id")

    workers = _read_dataset(WORKER_FILE)
    _require_columns(workers, {"firm_id", "covid", "total_contributions_q100"}, label=str(WORKER_FILE))

    prod = (
        workers[workers["covid"] == 1]
        .groupby("firm_id", observed=False)["total_contributions_q100"]
        .mean()
        .rename("q100")
    )
    firms = firms.merge(prod, on="firm_id", how="left")
    firms["is_remote"] = np.where(firms["remote"].isna(), np.nan, firms["remote"] > REMOTE_THRESHOLD)
    remote_limits = compute_padded_limits(
        firms_unique["remote"].dropna(),
        pad_ratio=0.05,
        min_span=0.05,
        lower_bound=0.0,
        upper_bound=1.0,
    )
    return firms_unique, remote_limits


def main() -> None:
    ensure_dir(OUTPUT.parent)
    firms_unique, remote_limits = _load_inputs()
    data = firms_unique[firms_unique["age"] < 100]
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=FIG_DPI)
    _style_axes(ax)

    grp_valid = data.dropna(subset=["age", "remote"])
    xs, ys = _binsreg_points(grp_valid, "age", "remote", FIRM_N_BINS)
    plt.plot(xs, ys, "o", linewidth=2.2, color="black", label="Binscatter", markeredgecolor='white', markeredgewidth=0.5)

    model = smf.ols("remote ~ age", data=grp_valid).fit()
    x_vals = np.linspace(grp_valid["age"].min(), grp_valid["age"].max(), 100)
    y_vals = model.predict(pd.DataFrame({"age": x_vals}))
    plt.plot(x_vals, y_vals, linewidth=2.2, color="black", label="OLS")

    anno_text = rf"$\beta = {model.params['age']:.2f}\;({model.bse['age']:.2f})$" "\n" rf"$R^2 = {model.rsquared:.2f}$"
    ax.text(
        0.95, 0.95, anno_text,
        transform=ax.transAxes, fontsize=11,
        verticalalignment="top", horizontalalignment="right",
        color="black",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.6, edgecolor="black"),
    )

    ax.tick_params(axis="both", labelsize=12)
    plt.xlabel("Firm age", fontsize=14)
    plt.ylabel("Remoteness score", fontsize=14)
    ax.set_ylim(*remote_limits)
    apply_standard_figure_layout(fig)
    fig.savefig(OUTPUT, dpi=FIG_DPI, facecolor="white")
    plt.close(fig)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
