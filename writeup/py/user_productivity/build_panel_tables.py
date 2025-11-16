#!/usr/bin/env python3
"""Generate separate OLS and IV tables for the core user productivity spec.

Historically ``build_baseline_table.py`` emitted a combined table with
Panel A (OLS) and Panel B (IV).  The write-up now needs these panels as
independent tables (Table 2 = OLS, Table 3 = IV).  This script re-uses the
existing helpers from the combined table generator to keep formatting
consistent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW

# Re-use helpers from the existing table builder
from build_baseline_table import (  # type: ignore
    OUTCOME_SETS,
    PREAMBLE_FLEX,
    build_panel_fe,
)

RAW_DIR = RESULTS_RAW


def load_user_productivity_results(variant: str) -> pd.DataFrame:
    """Return concatenated dataframe with baseline + alternative FE variants."""

    dir_alt = f"user_productivity_alternative_fe_{variant}"
    dir_init = f"user_productivity_initial_{variant}"

    input_alt = RAW_DIR / dir_alt / "consolidated_results.csv"
    input_init = RAW_DIR / dir_init / "consolidated_results.csv"

    if not input_init.exists():
        raise FileNotFoundError(f"Missing baseline results: {input_init}")
    if not input_alt.exists():
        raise FileNotFoundError(f"Missing alternative FE results: {input_alt}")

    df_init = pd.read_csv(input_init).copy()
    df_init["fe_tag"] = "init"

    df_alt = pd.read_csv(input_alt).copy()
    if "fe_tag" not in df_alt.columns:
        raise RuntimeError(
            f"Expected 'fe_tag' column in alternative FE results ({input_alt})"
        )

    return pd.concat([df_init, df_alt], ignore_index=True, sort=False)


def write_panel_table(
    *,
    df: pd.DataFrame,
    columns: list[tuple[str, str]],
    headers: dict[str, str],
    model: str,
    include_kp: bool,
    output_path: Path,
    panel_label: str | None = None,
) -> None:
    table_body = build_panel_fe(
        df,
        model,
        include_kp=include_kp,
        columns=columns,
        headers=headers,
        panel_label=panel_label,
    ).rstrip()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(PREAMBLE_FLEX + table_body + "\n")
    print(f"Wrote LaTeX table to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create separate OLS/IV tables for user productivity spec"
    )
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="User panel variant to load (default: %(default)s)",
    )
    parser.add_argument(
        "--outcome-set",
        choices=list(OUTCOME_SETS.keys()),
        default="total",
        help="Outcome set to render (default: %(default)s)",
    )
    args = parser.parse_args()

    config = OUTCOME_SETS[args.outcome_set]
    columns = config["columns"]  # type: ignore[assignment]
    headers = config["headers"]  # type: ignore[assignment]

    df = load_user_productivity_results(args.variant)

    suffix = config["filename_suffix"]  # type: ignore[index]
    if args.variant == "precovid" and not suffix:
        base_name = "user_productivity_precovid_total"
    else:
        base_name = f"user_productivity_{args.variant}{suffix}"

    output_dir = RESULTS_CLEANED_TEX
    path_ols = output_dir / f"{base_name}_panel_a_ols.tex"
    path_iv = output_dir / f"{base_name}_panel_b_iv.tex"

    write_panel_table(
        df=df,
        columns=columns,
        headers=headers,
        model="OLS",
        include_kp=False,
        output_path=path_ols,
        panel_label="A",
    )

    write_panel_table(
        df=df,
        columns=columns,
        headers=headers,
        model="IV",
        include_kp=True,
        output_path=path_iv,
        panel_label="B",
    )


if __name__ == "__main__":
    main()
