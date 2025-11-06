#!/usr/bin/env python3
"""Plot the startup × COVID effect across the full firm-age range."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from project_paths import DATA_PROCESSED, RESULTS_FINAL_FIGURES, ensure_dir, relative_to_project


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Residualise total_contributions_q100 on the canonical FE/controls, "
            "isolate the startup×COVID term (var4), and plot its partial effect "
            "across the full firm-age distribution."
        )
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DATA_PROCESSED / "user_panel_precovid.dta"),
        help="Stata panel file (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_FINAL_FIGURES / "startup_post_effect_by_age.png"),
        help="Destination for the plot (default: %(default)s).",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=50,
        help="Minimum observation count per age to display (default: %(default)s).",
    )
    parser.add_argument(
        "--max-age",
        type=float,
        default=None,
        help="Optional maximum age cutoff (default: use all).",
    )
    parser.add_argument("--dpi", type=int, default=200, help="Figure resolution in DPI.")
    parser.add_argument("--debug", action="store_true", help="Print coefficient diagnostics.")
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
    max_iter: int = 500,
) -> tuple[np.ndarray, float]:
    y = np.asarray(values, dtype=float)
    grand_mean = float(y.mean())
    effects = [np.zeros(len(counts)) for _, counts in indices]

    for _ in range(max_iter):
        max_change = 0.0
        for g, (codes, counts) in enumerate(indices):
            adjusted = y - grand_mean
            for h, (other_codes, _) in enumerate(indices):
                if h == g:
                    continue
                adjusted -= effects[h][other_codes]
            sums = np.bincount(codes, weights=adjusted, minlength=len(counts))
            new_eff = np.zeros_like(effects[g])
            mask = counts > 0
            new_eff[mask] = sums[mask] / counts[mask]
            if mask.any():
                max_change = max(max_change, np.abs(new_eff[mask] - effects[g][mask]).max())
            effects[g] = new_eff
        if max_change < tol:
            break

    resid = y - grand_mean
    for (codes, _), eff in zip(indices, effects):
        resid -= eff[codes]
    return resid, grand_mean


def demean_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
    indices: list[tuple[np.ndarray, np.ndarray]],
) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for col in columns:
        resid, _ = multiway_residual(df[col].to_numpy(), indices)
        out[col] = resid
    return out


def main() -> None:
    args = parse_args()
    needed = [
        "user_id",
        "firm_id",
        "yh",
        "age",
        "total_contributions_q100",
        "var3",
        "var4",
        "var5",
        "var6",
        "var7",
    ]
    panel = load_panel(args.input, needed)
    panel = panel.dropna(subset=needed)
    if args.max_age is not None:
        panel = panel[panel["age"] <= args.max_age]
    if panel.empty:
        raise ValueError("No observations remaining after filters.")

    fe_indices = [
        encode_fe(panel["user_id"]),
        encode_fe(panel["firm_id"]),
        encode_fe(panel["yh"]),
    ]

    demeaned = demean_columns(
        panel,
        [
            "total_contributions_q100",
            "var3",
            "var5",
            "var6",
            "var7",
            "var4",
        ],
        fe_indices,
    )

    y = demeaned["total_contributions_q100"]
    controls = [demeaned[c] for c in ["var3", "var5", "var6", "var7", "var4"]]
    X = np.column_stack(controls)
    names = ["var3", "var5", "var6", "var7", "var4"]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    coeffs = dict(zip(names, beta))
    if args.debug:
        for name in names:
            print(f"{name:>4s}: {coeffs[name]: .4f}")

    residuals = y - X @ beta
    var4_effect = coeffs["var4"] * demeaned["var4"]
    partial = residuals + var4_effect

    panel = panel.assign(partial_var4=partial)
    summary = (
        panel.groupby("age")
        .partial_var4.agg(["mean", "count"])
        .rename(columns={"mean": "effect", "count": "n"})
        .reset_index()
    )
    summary = summary[summary["n"] >= args.min_count]
    if summary.empty:
        raise ValueError("No age bins meet the min-count requirement.")

    output_path = ensure_dir(Path(args.output).resolve().parent) / Path(args.output).name

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(summary["age"], summary["effect"], marker="o", color="#1f77b4")
    ax.axhline(0.0, color="#aaaaaa", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Firm age (years)")
    ax.set_ylabel("Startup × COVID effect (partial residual)")
    ax.set_title("Startup status effect across firm age")
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    ax.text(
        0.02,
        0.05,
        "Controls: var3, var5, var6, var7 \nFEs: user, firm, year-half",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
        verticalalignment="bottom",
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=args.dpi)
    print(f"✓ Figure saved to {output_path}")


if __name__ == "__main__":
    main()
