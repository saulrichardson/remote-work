#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

PY_DIR = PROJECT_ROOT / "src" / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

from project_paths import RESULTS_CLEANED_TEX, RESULTS_RAW
from mechanisms_table_common import write_mechanisms_tables


DEFAULT_VARIANT = "precovid"

parser = argparse.ArgumentParser(description="Create post-control mechanisms latex table")
parser.add_argument(
    "--variant",
    choices=["unbalanced", "balanced", "precovid", "balanced_pre"],
    default=DEFAULT_VARIANT,
    help="Which user_panel sample variant to load (default: %(default)s)",
)
args = parser.parse_args()

variant = args.variant

specname = f"user_mechanisms_with_growth_{variant}"
input_csv = RESULTS_RAW / specname / "consolidated_results.csv"
output_tex_base = RESULTS_CLEANED_TEX / f"user_mechanisms_post_control_{variant}.tex"
output_tex_ols = RESULTS_CLEANED_TEX / f"user_mechanisms_post_control_{variant}_ols.tex"
output_tex_iv = RESULTS_CLEANED_TEX / f"user_mechanisms_post_control_{variant}_iv.tex"

write_mechanisms_tables(
    input_csv=input_csv,
    output_tex_base=output_tex_base,
    output_tex_ols=output_tex_ols,
    output_tex_iv=output_tex_iv,
)

print(f"Wrote {output_tex_ols}")
print(f"Wrote {output_tex_iv}")
print(f"Wrote {output_tex_base}")
