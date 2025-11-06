#!/usr/bin/env python3
"""Visualise the `var5` effect across firm age bins (spec-consistent)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from project_paths import (
    DATA_PROCESSED,
    RESULTS_FINAL_FIGURES,
    ensure_dir,
    relative_to_project,
)

CONTROL_COLS: tuple[str, ...] = ("var3", "var4", "var6", "var7")


@dataclass(frozen=True)
class FEIndex:
    """Container for encoded indices used in multi-way demeaning."""

    codes: np.ndarray
    count: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replicate the user_productivity.do specification and plot the "
            "var5 (remote × covid × startup) contribution against firm age."
        )
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DATA_PROCESSED / "user_panel_precovid.dta"),
        help="Processed Stata panel (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_FINAL_FIGURES / "var5_effect_by_age.png"),
        help="Destination for the figure (default: %(default)s).",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=10,
        help="Minimum firm-period observations required to plot a point.",
    )
    parser.add_argument(
        "--age-bin-width",
        type=int,
        default=2,
        help="Width of bins (in years) when aggregating by age.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Figure resolution (default: %(default)s).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print coefficient diagnostics.",
    )
    return parser.parse_args()


def _read_stata(path: Path, columns: Iterable[str]) -> pd.DataFrame:
    try:
        return pd.read_stata(path, columns=list(columns), convert_categoricals=False)
    except UnicodeDecodeError:
        return pd.read_stata(
            path,
            columns=list(columns),
            convert_categoricals=False,
            encoding="latin-1",
        )


def load_panel(path: str | Path, columns: Iterable[str]) -> pd.DataFrame:
    path = relative_to_project(path)
    if path.suffix.lower() != ".dta":
        return pd.read_csv(path, usecols=list(columns))
    return _read_stata(path, columns)


def encode_fe(series: pd.Series) -> FEIndex:
    codes, _ = pd.factorize(series, sort=True)
    codes = codes.astype(np.int32, copy=False)
    count = np.bincount(codes)
    return FEIndex(codes=codes, count=count)


def multiway_residual(
    values: np.ndarray,
    fe_indices: tuple[FEIndex, ...],
    *,
    tol: float = 1e-8,
    max_iter: int = 500,
) -> tuple[np.ndarray, float]:
    """Remove multiple sets of additive fixed effects via alternating projections."""
    y = np.asarray(values, dtype=float)
    grand_mean = float(np.mean(y))
    effects = [np.zeros(idx.count.size) for idx in fe_indices]

    for _ in range(max_iter):
        max_change = 0.0
        for g, fe in enumerate(fe_indices):
            adjusted = y - grand_mean
            for h, other in enumerate(fe_indices):
                if h == g:
                    continue
                adjusted -= effects[h][other.codes]

            sums = np.bincount(fe.codes, weights=adjusted, minlength=fe.count.size)
            new_eff = np.zeros_like(effects[g])
            mask = fe.count > 0
            new_eff[mask] = sums[mask] / fe.count[mask]

            if mask.any():
                change = np.abs(new_eff[mask] - effects[g][mask]).max()
                max_change = max(max_change, change)
            effects[g] = new_eff

        if max_change < tol:
            break

    residual = y - grand_mean
    for eff, fe in zip(effects, fe_indices):
        residual -= eff[fe.codes]
    return residual, grand_mean


def demean_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
    fe_indices: tuple[FEIndex, ...],
) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for col in columns:
        residual, _ = multiway_residual(df[col].to_numpy(), fe_indices)
        out[col] = residual
    return out


def bin_edges(max_age: float, width: int) -> np.ndarray:
    upper = int(np.ceil((max_age + 1) / width) * width)
    return np.arange(0, upper + width, width)


def main() -> None:
    args = parse_args()

    needed = {
        "user_id",
        "firm_id",
        "yh",
        "total_contributions_q100",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
        "age",
        "startup",
        "remote",
        "covid",
    }
    panel = load_panel(args.input, needed)
    panel = panel.dropna(subset=needed)
    if panel.empty:
        raise ValueError("No usable observations after dropping missing values.")

    user_fe = encode_fe(panel["user_id"])
    firm_fe = encode_fe(panel["firm_id"])
    period_fe = encode_fe(panel["yh"])
    fe_tuple = (user_fe, firm_fe, period_fe)

    demeaned = demean_columns(
        panel,
        [
            "total_contributions_q100",
            "var5",
            "var3",
            "var4",
            "var6",
            "var7",
        ],
        fe_tuple,
    )

    y_tilde = demeaned["total_contributions_q100"]
    x_cols = ["var3", "var4", "var5", "var6", "var7"]
    X = np.column_stack([demeaned[col] for col in x_cols])
    beta, *_ = np.linalg.lstsq(X, y_tilde, rcond=None)
    beta_map = dict(zip(x_cols, beta))

    residuals = y_tilde - X @ beta
    var5_tilde = demeaned["var5"]
    var5_effect = beta_map["var5"] * var5_tilde
    partial_resid = residuals + var5_effect

    if args.debug:
        print("Coefficients:")
        for name, value in beta_map.items():
            print(f"  {name:>4s} : {value: .4f}")
        mse = (residuals @ residuals) / len(residuals)
        print(f"MSE: {mse:.4f}")

    panel = panel.assign(
        var5_effect=var5_effect,
        var5_partial=partial_resid,
        period=np.where(panel["covid"] == 1, "Post", "Pre"),
    )

    startup_subset = panel.query("startup == 1")
    if startup_subset.empty:
        raise ValueError("Startup subset is empty; check input data.")

    agg = (
        startup_subset.groupby(["firm_id", "period"], observed=True)
        .agg(
            age=("age", "mean"),
            effect=("var5_effect", "mean"),
            partial=("var5_partial", "mean"),
            remote_share=("remote", "mean"),
            n_obs=("var5_effect", "size"),
        )
        .reset_index()
    )
    agg = agg[agg["n_obs"] >= args.min_observations]
    if agg.empty:
        raise ValueError("No firm-period groups survived the minimum observation filter.")

    bins = bin_edges(agg["age"].max(), args.age_bin_width)
    agg["age_bin"] = pd.cut(agg["age"], bins=bins, include_lowest=True)

    bin_summary = (
        agg.groupby(["age_bin", "period"], observed=True)
        .agg(
            age_mid=("age", "mean"),
            effect_mean=("effect", "mean"),
            partial_mean=("partial", "mean"),
            weight=("n_obs", "sum"),
        )
        .reset_index()
    ).dropna(subset=["age_mid"])

    output_path = ensure_dir(Path(args.output).resolve().parent) / Path(args.output).name

    fig, ax = plt.subplots(figsize=(7.5, 5))
    palette = {"Pre": "#1f77b4", "Post": "#d62728"}
    for period, group in bin_summary.groupby("period", observed=True):
        ax.scatter(
            group["age_mid"],
            group["partial_mean"],
            s=np.clip(group["weight"], 10, 200),
            alpha=0.8,
            color=palette.get(period, "#7f7f7f"),
            label=f"{period} (bins={len(group)})",
        )

    ax.axhline(0.0, color="#888888", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Firm age (years)")
    ax.set_ylabel("Partial residual of productivity attributed to var5")
    ax.set_title("Startup remote effect (var5) across firm age bins")
    ax.legend(frameon=False)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=args.dpi)
    print(f"✓ Figure saved to {output_path}")


if __name__ == "__main__":
    main()
