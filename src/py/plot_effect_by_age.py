#!/usr/bin/env python3
"""Plot FE-residualised effects (var3/var4/var5) across firm age."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from project_paths import DATA_PROCESSED, RESULTS_FINAL_FIGURES, ensure_dir, relative_to_project


EFFECT_CONFIG = {
    "var3": {
        "label_treat": "Remote × COVID",
        "label_base": "Baseline",
        "sample_filter": None,
        "max_age": None,
        "controls": ["var4", "var5"],
    },
    "var4": {
        "label_treat": "Startup × COVID",
        "label_base": "Non-startup / Pre",
        "sample_filter": None,
        "max_age": 10,
        "controls": ["var3", "var5"],
    },
    "var5": {
        "label_treat": "Startup remote × COVID",
        "label_base": "Startup baseline",
        "sample_filter": ("startup", 1),
        "max_age": 10,
        "controls": ["var3", "var4"],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FE-consistent effect plot across firm ages.")
    parser.add_argument("--input", type=str, default=str(DATA_PROCESSED / "user_panel_precovid.dta"))
    parser.add_argument("--effect", type=str, choices=EFFECT_CONFIG.keys(), default="var5")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Destination figure; defaults to results/final/figures/effect_<effect>_age.png",
    )
    parser.add_argument("--min-count", type=int, default=80, help="Min observations per age bin.")
    parser.add_argument("--dpi", type=int, default=250)
    parser.add_argument("--debug", action="store_true", help="Print coefficient table.")
    return parser.parse_args()


def load_panel(path: str | Path, columns: Iterable[str]) -> pd.DataFrame:
    path = relative_to_project(path)
    if path.suffix.lower() == ".dta":
        try:
            return pd.read_stata(path, columns=list(columns), convert_categoricals=False)
        except UnicodeDecodeError:
            return pd.read_stata(path, columns=list(columns), convert_categoricals=False, encoding="latin-1")
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
    grand = float(y.mean())
    effects = [np.zeros(len(cnt)) for _, cnt in indices]
    for _ in range(max_iter):
        max_change = 0.0
        for g, (codes, counts) in enumerate(indices):
            adjusted = y - grand
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
    resid = y - grand
    for (codes, _), eff in zip(indices, effects):
        resid -= eff[codes]
    return resid, grand


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


def aggregate_effect(df: pd.DataFrame, min_count: int) -> pd.DataFrame:
    grouped = df.groupby("age").agg(effect=("partial", "mean"), n=("partial", "count"), std=("partial", "std"))
    grouped = grouped[grouped["n"] >= min_count].reset_index()
    grouped["se"] = grouped["std"] / np.sqrt(grouped["n"])
    grouped["ci"] = 1.96 * grouped["se"]
    return grouped


def main() -> None:
    args = parse_args()
    cfg = EFFECT_CONFIG[args.effect]

    cols = ["user_id", "firm_id", "yh", "age", "total_contributions_q100", "var3", "var4", "var5", "startup"]
    panel = load_panel(args.input, cols)
    panel = panel.dropna(subset=["user_id", "firm_id", "yh", "age", "total_contributions_q100"])
    if cfg["sample_filter"]:
        col, val = cfg["sample_filter"]
        panel = panel[panel[col] == val]
    if cfg["max_age"] is not None:
        panel = panel[panel["age"] <= cfg["max_age"]]
    if panel.empty:
        raise ValueError("Empty sample after applying filters.")

    fe_idx = [encode_fe(panel["user_id"]), encode_fe(panel["firm_id"]), encode_fe(panel["yh"])]

    regressors = cfg["controls"] + [args.effect]
    demeaned = demean_columns(panel, ["total_contributions_q100", *regressors], fe_idx)
    X = np.column_stack([demeaned[c] for c in regressors])
    y = demeaned["total_contributions_q100"]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    coeffs = dict(zip(regressors, beta))
    if args.debug:
        for name in regressors:
            print(f"{name:>4s}: {coeffs[name]: .4f}")

    residuals = y - X @ beta
    effect_partial = residuals + coeffs[args.effect] * demeaned[args.effect]
    panel = panel.assign(partial=effect_partial)

    summary = aggregate_effect(panel, args.min_count)

    output = args.output
    if output is None:
        output = RESULTS_FINAL_FIGURES / f"effect_{args.effect}_age_python.png"
    output_path = ensure_dir(Path(output).resolve().parent) / Path(output).name

    fig, ax = plt.subplots(figsize=(8.2, 4.5))
    ax.plot(summary["age"], summary["effect"], marker="o", color="#1f77b4")
    ax.fill_between(
        summary["age"],
        summary["effect"] - summary["ci"],
        summary["effect"] + summary["ci"],
        color="#1f77b4",
        alpha=0.15,
        linewidth=0,
    )
    ax.axhline(0.0, color="#999999", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Firm age (years)")
    ax.set_ylabel(f"{args.effect} partial effect (FE residual)")
    ax.set_title(f"{args.effect} effect across firm age")
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=args.dpi)
    print(f"✓ Saved {output_path}")


if __name__ == "__main__":
    main()
