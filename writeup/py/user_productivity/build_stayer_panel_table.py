#!/usr/bin/env python3
"""Build a Table 2/3 style combined OLS+IV table for the stayer sample."""

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

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW  # type: ignore
from build_baseline_table import (  # type: ignore
    OUTCOME_SETS,
    build_combined_table,
)


def load_stayer_results(variant: str) -> pd.DataFrame:
    init_path = RESULTS_RAW / f"user_productivity_initial_{variant}_stayer" / "consolidated_results.csv"
    alt_path = RESULTS_RAW / f"user_productivity_alternative_fe_{variant}_stayer" / "consolidated_results.csv"

    if not init_path.exists():
        raise FileNotFoundError(init_path)
    if not alt_path.exists():
        raise FileNotFoundError(alt_path)

    df_init = pd.read_csv(init_path)
    df_init["fe_tag"] = "init"

    df_alt = pd.read_csv(alt_path)
    if "fe_tag" not in df_alt.columns:
        raise RuntimeError("Expected fe_tag column in alternative FE stayer results")

    return pd.concat([df_init, df_alt], ignore_index=True, sort=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
        default="precovid",
        help="User panel variant (default: %(default)s)",
    )
    args = parser.parse_args()

    df = load_stayer_results(args.variant)
    # Custom column set for stayers: drop match-FE columns, keep firm+user FE only.
    columns = [
        ("total_contributions_q100", "init"),   # no interaction, firm + user + time FE
        ("total_contributions_q100", "fyhu"),   # interaction, firm + user + time FE
        ("total_contributions_we",   "fyhu"),   # winsorised level outcome, same FE
    ]
    headers = {
        "total_contributions_q100": "Contribution Rank",
        "total_contributions_we": "Total",
    }

    table_tex = build_combined_table(df, columns=columns, headers=headers)
    # Drop the unused Firm×Individual FE row (no match FE columns in this layout).
    filtered = "\n".join(
        line for line in table_tex.splitlines()
        if "Firm $\\times$ Individual" not in line
    )

    out_name = f"user_productivity_{args.variant}_stayer_table3.tex"
    out_path = RESULTS_CLEANED_TEX / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(filtered + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
