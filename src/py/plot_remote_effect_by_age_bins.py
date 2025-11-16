#!/usr/bin/env python3
"""Plot remote post-COVID effects across firm age bins using spec-consistent residuals."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from project_paths import (
    DATA_PROCESSED,
    RESULTS_CLEANED_FIGURES,
    ensure_dir,
    relative_to_project,
)

DEFAULT_BINS: Sequence[float] = (0, 5, 10, 15, 20, 30, 40, 60, 1000)
BASE_COLS = ["var3", "var4", "var6", "var7"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extend the user_productivity specification by interacting "
            "remote × covid with firm-age bins, then plot the estimated "
            "remote effect across the full age distribution."
        )
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DATA_PROCESSED / "user_panel_precovid.dta"),
        help="Processed user panel (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_CLEANED_FIGURES / "remote_effect_by_age_bins.png"),
        help="Destination for the figure (default: %(default)s).",
    )
    parser.add_argument(
        "--age-bins",
        type=str,
        default=",".join(str(x) for x in DEFAULT_BINS),
        help="Comma-separated age breakpoints (inclusive lower bound). "
        "Last value is treated as the upper bound.",
    )
    parser.add_argument(
        "--min-firm-obs",
        type=int,
        default=10,
        help="Minimum worker observations per firm-period cell.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Figure resolution in DPI.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print coefficient diagnostics.",
    )
    return parser.parse_args()


def load_panel(path: str | Path, columns: Iterable[str]) -> pd.DataFrame:
    path = relative_to_project(path)
    if path.suffix.lower() == ".dta":
        try:
            return pd.read_stata(path, columns=list(columns), convert_categoricals=False)
        except UnicodeDecodeError:
            return pd.read_stata(
                path,
                columns=list(columns),
                convert_categoricals=False,
                encoding="latin-1",
            )
    return pd.read_csv(path, usecols=list(columns))


def encode_fe(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    codes, uniques = pd.factorize(series, sort=True)
    counts = np.bincount(codes.astype(np.int64), minlength=len(uniques))
    return codes.astype(np.int64), counts


def multiway_residual(
    values: np.ndarray,
    indices: list[tuple[np.ndarray, np.ndarray]],
    tol: float = 1e-8,
    max_iter: int = 400,
) -> tuple[np.ndarray, float]:
    y = np.asarray(values, dtype=float)
    mean = float(y.mean())
    effects = [np.zeros(len(counts)) for _, counts in indices]

    for _ in range(max_iter):
        max_change = 0.0
        for g, (codes, counts) in enumerate(indices):
            adjusted = y - mean
            for h, (other_codes, _) in enumerate(indices):
                if h == g:
                    continue
                adjusted -= effects[h][other_codes]
            sums = np.bincount(codes, weights=adjusted, minlength=len(counts))
            new_eff = np.zeros_like(effects[g])
            mask = counts > 0
            new_eff[mask] = sums[mask] / counts[mask]
            if mask.any():
                change = np.abs(new_eff[mask] - effects[g][mask]).max()
                max_change = max(max_change, change)
            effects[g] = new_eff
        if max_change < tol:
            break

    resid = y - mean
    for (codes, _), eff in zip(indices, effects):
        resid -= eff[codes]
    return resid, mean


def demean_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
    indices: list[tuple[np.ndarray, np.ndarray]],
) -> dict[str, np.ndarray]:
    results: dict[str, np.ndarray] = {}
    for col in columns:
        resid, _ = multiway_residual(df[col].to_numpy(), indices)
        results[col] = resid
    return results


def parse_bins(spec: str) -> np.ndarray:
    edges = np.array([float(x) for x in spec.split(",") if x.strip() != ""], dtype=float)
    if edges.size < 2:
        raise ValueError("Specify at least two age cut points.")
    if not np.all(np.diff(edges) > 0):
        raise ValueError("Age bins must be strictly increasing.")
    return edges


def assign_bins(ages: pd.Series, edges: np.ndarray) -> pd.Categorical:
    return pd.cut(
        ages,
        bins=edges,
        include_lowest=True,
        right=False,
        labels=[f"{int(edges[i])}–{int(edges[i+1])}" for i in range(len(edges) - 1)],
    )


def build_design_matrix(
    demeaned: dict[str, np.ndarray],
    bin_dummies: dict[str, np.ndarray],
) -> tuple[np.ndarray, list[str]]:
    X_parts = [demeaned[col] for col in BASE_COLS]
    names = BASE_COLS.copy()
    for name, vec in bin_dummies.items():
        X_parts.append(vec)
        names.append(name)
    return np.column_stack(X_parts), names


def main() -> None:
    args = parse_args()
    edges = parse_bins(args.age_bins)
    columns = [
        "user_id",
        "firm_id",
        "yh",
        "age",
        "startup",
        "remote",
        "covid",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
        "total_contributions_q100",
    ]
    panel = load_panel(args.input, columns)
    panel = panel.dropna(subset=columns)
    if panel.empty:
        raise ValueError("No observations after dropping missing values.")

    user_idx = encode_fe(panel["user_id"])
    firm_idx = encode_fe(panel["firm_id"])
    time_idx = encode_fe(panel["yh"])
    indices = [user_idx, firm_idx, time_idx]

    baseline_cols = ["total_contributions_q100", *BASE_COLS]
    demeaned = demean_columns(panel, baseline_cols, indices)

    remote_covid = panel["remote"] * panel["covid"]
    panel = panel.assign(remote_covid=remote_covid)

    age_bins = assign_bins(panel["age"], edges)
    panel = panel.assign(age_bin=age_bins)
    counts = panel["age_bin"].value_counts()
    bin_levels = [lvl for lvl in age_bins.cat.categories if counts.get(lvl, 0) > 0]
    if len(bin_levels) < 2:
        raise ValueError("Need at least 2 populated age bins.")

    # Drop last bin as baseline
    interaction_cols: dict[str, np.ndarray] = {}
    for level in bin_levels[:-1]:
        dummy = (panel["age_bin"] == level).astype(float)
        interaction = demean_columns(
            pd.DataFrame({"interaction": remote_covid * dummy}), ["interaction"], indices
        )["interaction"]
        interaction_cols[f"remote_covid_{level}"] = interaction

    X, names = build_design_matrix(demeaned, interaction_cols)
    y = demeaned["total_contributions_q100"]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    coeffs = dict(zip(names, beta))

    if args.debug:
        for name in names:
            print(f"{name:>20s}: {coeffs[name]: .4f}")

    remote_effect = coeffs["var3"] * demeaned["var3"]
    for name, vec in interaction_cols.items():
        remote_effect += coeffs[name] * vec

    panel = panel.assign(
        remote_effect=remote_effect,
        period=np.where(panel["covid"] == 1, "Post", "Pre"),
    )

    agg = (
        panel.groupby(["firm_id", "period", "age_bin"], observed=True)
        .agg(
            age=("age", "mean"),
            effect=("remote_effect", "mean"),
            n_obs=("remote_effect", "size"),
        )
        .reset_index()
    )
    agg = agg[agg["n_obs"] >= args.min_firm_obs]
    agg = agg[agg["period"] == "Post"]  # remote effect only active post-COVID
    if agg.empty:
        raise ValueError("No firm-period groups survived the filters.")

    summary = (
        agg.groupby("age_bin", observed=True)
        .agg(
            age_mid=("age", "mean"),
            effect_mean=("effect", "mean"),
            weight=("n_obs", "sum"),
        )
        .reset_index()
    )
    summary = summary.dropna(subset=["age_mid"])

    output_path = ensure_dir(Path(args.output).resolve().parent) / Path(args.output).name

    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.scatter(
        summary["age_mid"],
        summary["effect_mean"],
        s=np.clip(summary["weight"], 30, 400),
        c="#1f77b4",
        alpha=0.85,
        edgecolors="black",
        linewidths=0.4,
    )
    ax.set_xlabel("Firm age (years)")
    ax.set_ylabel("Remote × COVID effect (predicted contribution)")
    ax.set_title("Remote post-COVID effect across firm age bins")
    for _, row in summary.iterrows():
        ax.annotate(
            row["age_bin"],
            (row["age_mid"], row["effect_mean"]),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=8,
        )
    ax.axhline(0, color="#888", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=args.dpi)
    print(f"✓ Figure saved to {output_path}")


if __name__ == "__main__":
    main()
