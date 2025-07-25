#!/usr/bin/env python3
"""Wrapper: build LaTeX table for *binned* LEAN firm mechanisms."""

from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent

ORIG = HERE / "create_firm_mechanisms_lean_table.py"

spec = importlib.util.spec_from_file_location("firm_mech_lean_orig", ORIG)
module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec and spec.loader
spec.loader.exec_module(module)  # type: ignore[arg-type]


def _patched_main():
    module.INPUT_CSV = (
        Path(module.PROJECT_ROOT)
        / "results"
        / "raw"
        / "firm_mechanisms_lean_binned"
        / "consolidated_results.csv"
    )

    module.OUTPUT_TEX = (
        Path(module.PROJECT_ROOT)
        / "results"
        / "cleaned"
        / "firm_mechanisms_lean_binned.tex"
    )

    module.main()


if __name__ == "__main__":
    _patched_main()
