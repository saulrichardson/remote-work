#!/usr/bin/env python3
"""Generate LaTeX tables for *binned* user mechanism tests.

This is a thin wrapper around `create_user_mechanisms_table.py` that merely
changes the expected input directory prefix from
`results/raw/user_mechanisms_<variant>` to
`results/raw/user_mechanisms_binned_<variant>`.

All remaining logic is inherited verbatim by importing the original builder
as a module and invoking its `main()` after monkey-patching the constant names
it uses to locate the raw CSV.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ORIG_PATH = HERE / "create_user_mechanisms_table.py"

# ---------------------------------------------------------------------------
# Dynamically import the original builder so we can tweak its global vars
# before running `main()`.
# ---------------------------------------------------------------------------

spec = importlib.util.spec_from_file_location("user_mech_orig", ORIG_PATH)
module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec and spec.loader
spec.loader.exec_module(module)  # type: ignore[arg-type]

# Overwrite the SPECNAME resolution to look for *binned* outputs ------------

def _patched_input_dir(variant: str) -> Path:
    """Return Path to results/raw/user_mechanisms_binned_<variant>."""
    root = Path(module.PROJECT_ROOT) / "results" / "raw"
    return root / f"user_mechanisms_binned_{variant}"

# Patch helper inside the imported module
# It builds `SPECNAME` directly, so we simply monkey-patch the constant.
module.SPECNAME_TEMPLATE = "user_mechanisms_binned_{variant}"

def _patched_main():  # wraps original main but injects our directory logic
    # Monkey-patch the part that sets INPUT_CSV / OUTPUT_TEX before main runs
    variant = module.args.variant
    input_dir = _patched_input_dir(variant)
    module.INPUT_CSV = input_dir / "consolidated_results.csv"
    # Output file name mirrors original, but with `_binned` suffix for clarity
    module.OUTPUT_TEX = (
        Path(module.PROJECT_ROOT)
        / "results"
        / "cleaned"
        / f"user_mechanisms_binned_{variant}.tex"
    )

    # Now delegate to the unchanged main implementation
    module.main()


if __name__ == "__main__":
    _patched_main()
