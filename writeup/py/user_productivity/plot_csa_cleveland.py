#!/usr/bin/env python3
"""Plot CSA-specific OLS estimates (var5) as a Cleveland-style chart."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
SRC_PY = PROJECT_ROOT / "src" / "py"
if str(SRC_PY) not in sys.path:
    sys.path.insert(0, str(SRC_PY))

from project_paths import RESULTS_CLEANED_FIGURES, RESULTS_RAW, ensure_dir  # noqa: E402
from plot_style import (  # noqa: E402
    ERROR_COLOR,
    FIGSIZE,
    SERIES_COLOR,
    TICK_LABEL_SIZE,
    apply_mpl_defaults,
    compute_padded_limits,
    style_axes,
)

apply_mpl_defaults()

# Match the startup-cutoff plots: use LaTeX for math labels and Palatino font.
plt.rcParams.update(
    {
        "text.usetex": True,
        "text.latex.preamble": r"\usepackage{amsmath}\usepackage{palatino}",
    }
)

CI_SCALE = 1.96
BETA_LABEL = r"$\beta_{ \text{Remote} \times \mathbf{1}(\text{Post}) \times \text{Startup} }$"


def _default_paths(panel_variant: str) -> tuple[Path, Path]:
    base_dir = RESULTS_RAW / f"user_productivity_csa_interactions_{panel_variant}"
    csv_path = base_dir / "consolidated_results_by_csa.csv"
    fig_path = RESULTS_CLEANED_FIGURES / f"top_employment_csa_remote_startup_{panel_variant}.png"
    return csv_path, fig_path


def _wrap_label(name: str) -> str:
    """Split long labels into at most two lines with balanced lengths."""
    text = name.strip()
    if not text:
        return text

    hyphen_positions = [idx for idx, char in enumerate(text) if char == "-"]
    if hyphen_positions:
        lengths = [
            abs(len(text[:pos + 1].strip()) - len(text[pos + 1 :].strip()))
            for pos in hyphen_positions
        ]
        best = hyphen_positions[int(np.argmin(lengths))]
        left = text[: best + 1].strip()
        right = text[best + 1 :].strip()
        if left and right:
            return f"{left}\n{right}"

    if ", " in text:
        left, right = text.split(", ", 1)
        return f"{left}\n{right.strip()}"

    return text


def _load_data(path: Path, *, name_column: str, sort_column: str | None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing input CSV: {path}")
    df = pd.read_csv(path)
    subset = df[(df["model_type"] == "OLS") & (df["param"] == "var5")].copy()
    if subset.empty:
        raise ValueError("No OLS var5 rows found in the provided CSV.")
    if name_column not in subset.columns:
        raise KeyError(f"Column `{name_column}` not present in {path}")
    if sort_column:
        if sort_column not in subset.columns:
            raise KeyError(f"Column `{sort_column}` not present in {path}")
        subset = subset.sort_values(sort_column).reset_index(drop=True)
    else:
        subset = subset.sort_values("coef").reset_index(drop=True)
    subset["ci"] = CI_SCALE * subset["se"]
    subset["label"] = subset[name_column].fillna("").astype(str).apply(_wrap_label)
    return subset


def _plot(df: pd.DataFrame, output: Path, *, title: str) -> None:
    n_obs = len(df)
    height = max(FIGSIZE[1], 0.55 * n_obs)
    width = max(FIGSIZE[0] + 1.2, 9.0)
    fig, ax = plt.subplots(figsize=(width, height))

    y_pos = np.arange(n_obs, dtype=float)
    ax.errorbar(
        df["coef"],
        y_pos,
        xerr=df["ci"],
        fmt="o",
        color=SERIES_COLOR,
        ecolor=ERROR_COLOR,
        elinewidth=1.4,
        capsize=4,
        markersize=5.5,
        markeredgecolor="white",
        markeredgewidth=0.7,
    )
    ax.axvline(0.0, color="#333333", linewidth=1.0, linestyle="--", alpha=0.8, zorder=0)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(df["label"])
    for label in ax.get_yticklabels():
        label.set_fontsize(max(TICK_LABEL_SIZE - 4, 9))
    ax.set_xlabel(BETA_LABEL)
    if title:
        ax.set_title(title)

    spread = np.concatenate([df["coef"].to_numpy(), df["coef"] - df["ci"], df["coef"] + df["ci"]])
    xmin, xmax = compute_padded_limits(spread, pad_ratio=0.2)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-0.5, n_obs - 0.5)
    ax.invert_yaxis()

    style_axes(ax, ygrid=True)
    fig.subplots_adjust(left=0.33, right=0.98, top=0.9, bottom=0.08)

    ensure_dir(output.parent)
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panel-variant",
        default="precovid",
        help="User panel variant to match the CSA interaction spec.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to consolidated_results_by_csa.csv (defaults based on panel variant).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination for the Cleveland chart PNG (defaults to cleaned figures dir).",
    )
    parser.add_argument(
        "--name-column",
        default="csa_name",
        help="Column containing the geographic label (default: csa_name).",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional figure title (omit for bare axis labels).",
    )
    parser.add_argument(
        "--sort-column",
        help=(
            "Column used to order the coefficients. Set to the employment rank (e.g., "
            "csa_rank or msa_rank) to mirror the pre-selected top list; default sorts by "
            "the point estimate."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    default_input, default_output = _default_paths(args.panel_variant)
    csv_path = args.input or default_input
    output_path = args.output or default_output

    df = _load_data(
        csv_path,
        name_column=args.name_column,
        sort_column=args.sort_column,
    )
    _plot(df, output_path, title=args.title)
    print(f"Saved Cleveland chart to {output_path}")


if __name__ == "__main__":
    main()
