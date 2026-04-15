#!/usr/bin/env python3
"""Generate LaTeX regression tables for the four *user‐productivity*
heterogeneity splits (modal MSA, distance, dynamic growth, post‐COVID
growth) so they can be embedded in *mini-report.tex*.

The script is a thin wrapper around the generic
``scripts/heterogeneity_table.py`` helper.  It merely maps the location of the raw
CSV files to cleaned output filenames and human-readable captions/labels.

Running the script is idempotent – it will overwrite any existing .tex files
with the same name so the Makefile can call it every time without worrying
about stale artefacts.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]

PY = sys.executable or "python"

# ---------------------------------------------------------------------------
#  Configure number of bins used for the heterogeneity splits
# ---------------------------------------------------------------------------
# Change this single constant to 2 to switch to a two-way split.  All input
# paths will adjust automatically (they expect the bin count as a suffix).

NBINS = 3  # default

# ---------------------------------------------------------------------------
#  Four heterogeneity result files → cleaned LaTeX names
# ---------------------------------------------------------------------------

RAW_BASE = PROJECT_ROOT / "results" / "raw"
CLEANED_DIR = PROJECT_ROOT / "results" / "cleaned"

TASKS = [
    {
        "csv": RAW_BASE / f"het_modal_base_precovid_{NBINS}" / "var5_modal_base.csv",
        "out": CLEANED_DIR / "var5_modal_base.tex",
        "caption": "Modal MSA heterogeneity (IV)",
        "label": "tab:modal_msa",
        "bucket_labels": ["Outside", "Inside", "Remote"],
    },
    {
        "csv": RAW_BASE / f"het_dist_base_precovid_{NBINS}" / "var5_distance_base.csv",
        "out": CLEANED_DIR / "var5_distance_base.tex",
        "caption": "Distance heterogeneity (IV)",
        "label": "tab:distance",
    },
    {
        "csv": RAW_BASE / f"dynamic_growth_base_precovid_{NBINS}" / "var5_growth_base.csv",
        "out": CLEANED_DIR / "var5_growth_base_dynamic.tex",
        "caption": "Dynamic growth heterogeneity (IV)",
        "label": "tab:dynamic_growth",
    },
    {
        "csv": RAW_BASE / f"post_growth_base_precovid_{NBINS}" / "var5_growth_base.csv",
        "out": CLEANED_DIR / "var5_growth_base_post.tex",
        "caption": "Post-COVID growth heterogeneity (IV)",
        "label": "tab:post_growth",
    },
]


def run_one(csv: Path, out: Path, caption: str, label: str, bucket_labels: list[str] | None = None) -> None:
    if not csv.exists():
        print(f"✗ {csv.relative_to(PROJECT_ROOT)} missing – skip")
        return

    cmd = [
        PY,
        str(PROJECT_ROOT / "scripts" / "heterogeneity_table.py"),
        str(csv),
        "--caption",
        caption,
        "--label",
        label,
        "--out",
        str(out),
    ]
    if bucket_labels:
        cmd += ["--bucket-labels", ",".join(bucket_labels)]

    subprocess.run(cmd, check=True)


def main() -> None:
    for t in TASKS:
        run_one(
            Path(t["csv"]),
            Path(t["out"]),
            t["caption"],
            t["label"],
            t.get("bucket_labels"),
        )


if __name__ == "__main__":
    main()
