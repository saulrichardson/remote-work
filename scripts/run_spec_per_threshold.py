#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Stata vacancy spec for multiple thresholds")
    p.add_argument("--outdir", required=True, help="Base outdir used in threshold sweep (e.g., data/processed/vacancy/sensitivity)")
    p.add_argument("--thresholds", nargs="+", type=int, required=True, help="Threshold-days list, e.g., 30 60 90 120 150")
    p.add_argument("--stata", default="/Applications/Stata/StataSE.app/Contents/MacOS/stata-se", help="Path to Stata executable")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base = Path(args.outdir)
    canonical_csv = Path("data/processed/vacancy/firm_halfyear_panel_MERGED_POST.csv")
    spec_dir = Path("spec")
    spec_file = spec_dir / "firm_scaling_vacancy_outcomes.do"
    results_base = Path("results/raw")
    results_canon_dir = results_base / "firm_scaling_vacancy_outcomes"
    spec_log_dir = Path("spec/log")
    log_canon = spec_log_dir / "firm_scaling_vacancy_outcomes.log"

    if not spec_file.exists():
        raise SystemExit(f"Spec file not found: {spec_file}")

    for thr in args.thresholds:
        thr_dir = base / f"t{thr}"
        post_csv = thr_dir / "firm_halfyear_panel_MERGED_POST.csv"
        if not post_csv.exists():
            raise SystemExit(f"Missing postprocessed CSV for threshold {thr}: {post_csv}")

        print(f"\n=== Running Stata spec for threshold {thr} ===")

        # 1) Copy per-threshold CSV into the canonical path used by the spec
        canonical_csv.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(post_csv, canonical_csv)

        # 2) Run Stata spec in batch mode from spec directory
        run([args.stata, "-b", "do", spec_file.name], cwd=spec_dir)

        # 3) Move results into threshold-specific directory
        thr_results_dir = results_base / f"firm_scaling_vacancy_outcomes_t{thr}"
        thr_results_dir.mkdir(parents=True, exist_ok=True)
        for fname in ("consolidated_results.csv", "first_stage.csv"):
            src = results_canon_dir / fname
            if src.exists():
                shutil.copy2(src, thr_results_dir / fname)
        # Also copy log
        if log_canon.exists():
            shutil.copy2(log_canon, spec_log_dir / f"firm_scaling_vacancy_outcomes_t{thr}.log")

        print(f"✓ Stata results stored in {thr_results_dir}")


if __name__ == "__main__":
    main()

