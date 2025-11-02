#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from project_paths import (
    DATA_PROCESSED,
    PY_DIR,
    RESULTS_RAW,
    SPEC_DIR,
    ensure_dir,
)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sweep --min-vacancies for postprocess and re-run Stata spec")
    p.add_argument("--merged", required=True, help="Path to firm_halfyear_panel_MERGED.csv (e.g., t90)")
    p.add_argument("--min-vacs", nargs="+", type=int, required=True, help="Values to test, e.g., 0 1 3 5")
    p.add_argument("--stata", default="/Applications/Stata/StataSE.app/Contents/MacOS/stata-se", help="Path to Stata executable")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    merged = Path(args.merged)
    if not merged.exists():
        raise SystemExit(f"Merged CSV not found: {merged}")

    postp_script = (PY_DIR / "postprocess_halfyear_panel.py").resolve()
    if not postp_script.exists():
        raise SystemExit(f"Missing postprocess script: {postp_script}")

    # Canonical path Stata spec reads
    canonical_csv = DATA_PROCESSED / "vacancy" / "firm_halfyear_panel_MERGED_POST.csv"
    ensure_dir(canonical_csv.parent)
    spec_dir = SPEC_DIR
    spec_file = spec_dir / "firm_scaling_vacancy_outcomes.do"
    if not spec_file.exists():
        raise SystemExit(f"Missing Stata spec: {spec_file}")

    results_base = RESULTS_RAW
    canon_results_dir = results_base / "firm_scaling_vacancy_outcomes"
    log_dir = SPEC_DIR / "log"

    for mv in args.min_vacs:
        print(f"\n=== Running sweep for min_vacancies={mv} ===")
        # 1) Postprocess with guard value
        out_dir = merged.parent / f"minvac_{mv}"
        ensure_dir(out_dir)
        out_csv = out_dir / "firm_halfyear_panel_MERGED_POST.csv"
        run([
            "python", str(postp_script),
            "--input", str(merged),
            "--output", str(out_csv),
            "--min-lag-employees", "100",
            "--min-vacancies", str(mv),
        ])

        # 2) Copy to canonical and run Stata
        shutil.copy2(out_csv, canonical_csv)
        run([args.stata, "-b", "do", spec_file.name], cwd=spec_dir)

        # 3) Save results under minvac-specific folder
        mv_results = ensure_dir(results_base / f"firm_scaling_vacancy_outcomes_minvac_{mv}")
        for fname in ("consolidated_results.csv", "first_stage.csv"):
            src = canon_results_dir / fname
            if src.exists():
                shutil.copy2(src, mv_results / fname)
        # copy log too
        src_log = log_dir / "firm_scaling_vacancy_outcomes.log"
        if src_log.exists():
            shutil.copy2(src_log, log_dir / f"firm_scaling_vacancy_outcomes_minvac_{mv}.log")
        print(f"✓ Stored results in {mv_results}")


if __name__ == "__main__":
    main()
