#!/usr/bin/env python3
"""
Run a sensitivity sweep over multiple fill thresholds for the vacancy panel.

For each threshold in --thresholds, this script:
  1) Builds firm×half-year vacancy metrics from Postings_scoop.csv
  2) Builds the final vacancy outcomes panel used by the paper

Outputs are written under --outdir/<threshold>/ ...

Example
  ./bin/archive-python src/archive/py/rendering_and_sweeps/run_vacancy_threshold_sweep.py \
    --input data/raw/vacancy/Postings_scoop.csv \
    --firm-panel data/samples/firm_panel.csv \
    --outdir data/clean/vacancy/sensitivity \
    --thresholds 30 60 90 120 150

Notes
  - This does not run the Stata spec; it only prepares the per-threshold CSVs.
  - You can pass --limit N to do a quick dry run on the first N rows.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path

from src.py.project_paths import PROJECT_ROOT, PY_DIR

ARCHIVE_PY_DIR = Path(__file__).resolve().parents[1]
ARCHIVE_PYTHON = PROJECT_ROOT / "bin" / "archive-python"
PAPER_PYTHON = PROJECT_ROOT / "bin" / "paper-python"

def run(cmd: list[str]) -> None:
    print("→", " ".join(shlex.quote(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sweep vacancy fill thresholds")
    p.add_argument("--input", required=True, help="Path to Postings_scoop.csv")
    p.add_argument("--firm-panel", required=True, help="Path to firm_panel.csv")
    p.add_argument("--outdir", required=True, help="Base output directory for per-threshold results")
    p.add_argument("--thresholds", nargs="+", type=int, required=True, help="List of threshold-days to test, e.g., 30 60 90 120 150")
    p.add_argument("--limit", type=int, default=0, help="Optional row limit for build_vacancy_halfyear_panel (0 = full)")
    p.add_argument("--progress-every", type=int, default=1_000_000, help="Progress cadence for build_vacancy_halfyear_panel (0 to disable)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    inp = Path(args.input)
    fp = Path(args.firm_panel)
    base_out = Path(args.outdir)
    base_out.mkdir(parents=True, exist_ok=True)

    # Resolve scripts
    outcomes_script = PY_DIR / "build_vacancy_outcomes_panel.py"
    for s in (ARCHIVE_PYTHON, PAPER_PYTHON, outcomes_script):
        if not s.exists():
            raise SystemExit(f"Required script not found: {s}")

    # Validate inputs
    if not inp.exists():
        raise SystemExit(f"Input CSV not found: {inp}")
    if not fp.exists():
        raise SystemExit(f"Firm panel CSV not found: {fp}")

    # 1) Build all threshold panels in one pass for speed
    multi_builder = ARCHIVE_PY_DIR / "nonpaper_builders" / "build_halfyear_panel_multi.py"
    if not multi_builder.exists():
        raise SystemExit(f"Missing multi-threshold builder: {multi_builder}")
    run([
        str(ARCHIVE_PYTHON), str(multi_builder),
        "--input", str(inp),
        "--outdir", str(base_out),
        "--thresholds", *[str(t) for t in args.thresholds],
        "--limit", str(args.limit),
        "--progress-every", str(args.progress_every),
    ])

    for thr in args.thresholds:
        out_dir = base_out / f"t{thr}"
        out_dir.mkdir(parents=True, exist_ok=True)

        panel_csv = out_dir / "firm_halfyear_panel.csv"
        post_csv = out_dir / "firm_halfyear_panel_MERGED_POST.csv"

        # 2) Build final vacancy outcomes panel
        run([
            str(PAPER_PYTHON), str(outcomes_script),
            "--vacancy-panel", str(panel_csv),
            "--firm-panel", str(fp),
            "--output", str(post_csv),
        ])

        print(f"✓ Threshold {thr}: outputs in {out_dir}")


if __name__ == "__main__":
    main()
