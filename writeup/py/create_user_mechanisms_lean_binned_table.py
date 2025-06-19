#!/usr/bin/env python3
"""Wrapper: build LaTeX table for *binned* LEAN user mechanism results.

Re-uses `create_user_mechanisms_lean_table.py` but points the input directory
to results/raw/user_mechanisms_lean_binned_<variant>/ and saves the cleaned
output as results/cleaned/user_mechanisms_lean_binned_<variant>.tex.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent

ORIG = HERE / "create_user_mechanisms_lean_table.py"

spec = importlib.util.spec_from_file_location("user_mech_lean_orig", ORIG)
module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec and spec.loader
spec.loader.exec_module(module)  # type: ignore[arg-type]


def _patched_main():
    variant = module.args.variant

    # point to binned directory
    root = Path(module.PROJECT_ROOT) / "results" / "raw"
    module.INPUT_CSV = root / f"user_mechanisms_lean_binned_{variant}" / "consolidated_results.csv"

    # adjust output filename
    module.OUTPUT_TEX = (
        Path(module.PROJECT_ROOT)
        / "results"
        / "cleaned"
        / f"user_mechanisms_lean_binned_{variant}.tex"
    )

    module.main()


if __name__ == "__main__":
    _patched_main()
