#!/usr/bin/env python3
"""Create standalone OLS and IV tables for the core user productivity spec.

This mirrors the formatting used by ``create_user_productivity_table.py`` but
splits the combined Panel A/B layout into two separate tables so they can be
displayed independently.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY_DIR = HERE.parents[1] / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_FINAL_TEX

from create_user_productivity_table import (  # type: ignore
    OUTCOME_SETS,
    PREAMBLE_FLEX,
    build_panel_fe,
)
from create_user_productivity_panel_tables import load_user_productivity_results  # type: ignore


def write_table(path: Path, table_body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PREAMBLE_FLEX + table_body + "\n")
    print(f"Wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create standalone OLS and IV user productivity tables"
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

    df = load_user_productivity_results(args.variant)
    config = OUTCOME_SETS[args.outcome_set]
    columns = config["columns"]  # type: ignore[assignment]
    headers = config["headers"]  # type: ignore[assignment]

    if args.variant == "precovid" and not config["filename_suffix"]:
        base_name = "user_productivity_precovid_total"
    else:
        base_name = f"user_productivity_{args.variant}{config['filename_suffix']}"

    output_dir = RESULTS_FINAL_TEX
    ols_path = output_dir / f"{base_name}_ols_single.tex"
    iv_path = output_dir / f"{base_name}_iv_single.tex"

    table_ols = build_panel_fe(
        df,
        model="OLS",
        include_kp=False,
        columns=columns,
        headers=headers,
        panel_label="A",
    )
    table_iv = build_panel_fe(
        df,
        model="IV",
        include_kp=True,
        columns=columns,
        headers=headers,
        panel_label="B",
    )

    write_table(ols_path, table_ols)
    write_table(iv_path, table_iv)


if __name__ == "__main__":
    main()
