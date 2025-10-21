#!/usr/bin/env python3
"""Build a compact report PDF with IV and OLS heterogeneity tables.

Steps:
- Ensure IV tables exist by calling the existing generator.
- If OLS CSVs exist, render them into LaTeX as well.
- Write a self-contained LaTeX doc that inputs the available tables.
- Optionally compile to PDF (left to caller/Makefile/CLI).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable or "python"

RAW = PROJECT_ROOT / "results" / "raw"
CLEAN = PROJECT_ROOT / "results" / "cleaned"
WRITEUP = PROJECT_ROOT / "writeup"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def find_first(*candidates: Path) -> Path | None:
    for c in candidates:
        if c.exists():
            return c
    return None


def main() -> None:
    # 1) Ensure IV tables exist
    run([PY, str(WRITEUP / "py" / "create_user_productivity_heterogeneity_tables.py")])

    # 2) If OLS CSVs exist, render OLS LaTeX
    # Modal MSA OLS
    modal_ols_csv = find_first(
        RAW / "het_modal_base_precovid_3" / "var5_modal_base_ols.csv",
        RAW / "het_modal_base_precovid_2" / "var5_modal_base_ols.csv",
    )
    if modal_ols_csv is not None:
        run([
            PY,
            str(PROJECT_ROOT / "scripts" / "heterogeneity_table.py"),
            str(modal_ols_csv),
            "--caption",
            "Modal MSA heterogeneity (OLS)",
            "--label",
            "tab:modal_msa_ols",
            "--bucket-labels",
            "Outside,Inside,Remote",
            "--out",
            str(CLEAN / "var5_modal_base_ols.tex"),
        ])

    # Distance OLS (support either 2 or 3 buckets)
    dist_ols_csv = find_first(
        RAW / "het_dist_base_precovid_3" / "var5_distance_base_ols.csv",
        RAW / "het_dist_base_precovid_2" / "var5_distance_base_ols.csv",
    )
    if dist_ols_csv is not None:
        run([
            PY,
            str(PROJECT_ROOT / "scripts" / "heterogeneity_table.py"),
            str(dist_ols_csv),
            "--caption",
            "Distance heterogeneity (OLS)",
            "--label",
            "tab:distance_ols",
            "--out",
            str(CLEAN / "var5_distance_base_ols.tex"),
        ])

    # 3) Build the master TeX file
    lines: list[str] = []
    lines += [
        "\\documentclass[11pt]{article}",
        "\\usepackage[margin=1in]{geometry}",
        "\\usepackage{float}",
        "\\usepackage{booktabs}",
        "\\usepackage{makecell}",
        "\\usepackage{amsmath}",
        "\\usepackage{dsfont}",
        "\\usepackage{caption}",
        "\\title{User Productivity — Heterogeneity (IV and OLS)}",
        "\\date{}",
        "\\begin{document}",
        "\\maketitle",
        "\\section*{Modal vs. Non-Modal MSA}",
        "Buckets: Outside (0), Inside (1), Remote (2).",
        "\\input{../results/cleaned/var5_modal_base.tex}",
    ]
    if (CLEAN / "var5_modal_base_ols.tex").exists():
        lines += ["\\input{../results/cleaned/var5_modal_base_ols.tex}"]
    lines += [
        "\\section*{Distance Heterogeneity}",
        "Firms are split into distance quantiles (3 or 2 bins).",
        "\\paragraph{Three bins (terciles).} Short / Medium / Long.",
    ]
    if (CLEAN / "var5_distance_base.tex").exists():
        lines += ["\\input{../results/cleaned/var5_distance_base.tex}"]
    if (CLEAN / "var5_distance_base_ols.tex").exists():
        lines += ["\\input{../results/cleaned/var5_distance_base_ols.tex}"]

    # Two-bin variant (halves)
    # If OLS/IV CSVs exist for 2 bins, render and include
    dist2_iv = RAW / "het_dist_base_precovid_2" / "var5_distance_base.csv"
    dist2_ols = RAW / "het_dist_base_precovid_2" / "var5_distance_base_ols.csv"
    if dist2_iv.exists():
        run([
            PY,
            str(PROJECT_ROOT / "scripts" / "heterogeneity_table.py"),
            str(dist2_iv),
            "--caption",
            "Distance heterogeneity (IV, 2 bins)",
            "--label",
            "tab:distance2",
            "--out",
            str(CLEAN / "var5_distance_base_2.tex"),
        ])
    if dist2_ols.exists():
        run([
            PY,
            str(PROJECT_ROOT / "scripts" / "heterogeneity_table.py"),
            str(dist2_ols),
            "--caption",
            "Distance heterogeneity (OLS, 2 bins)",
            "--label",
            "tab:distance2_ols",
            "--out",
            str(CLEAN / "var5_distance_base_ols_2.tex"),
        ])

    lines += [
        "\\paragraph{Two bins (halves).} Short / Long.",
    ]
    if (CLEAN / "var5_distance_base_2.tex").exists():
        lines += ["\\input{../results/cleaned/var5_distance_base_2.tex}"]
    if (CLEAN / "var5_distance_base_ols_2.tex").exists():
        lines += ["\\input{../results/cleaned/var5_distance_base_ols_2.tex}"]

    lines += [
        "\\end{document}",
        "",
    ]

    out_tex = WRITEUP / "user_heterogeneity_report.tex"
    out_tex.write_text("\n".join(lines))
    try:
        rel = out_tex.relative_to(Path.cwd())
    except Exception:
        rel = out_tex
    print(f"✓ Wrote {rel}")


if __name__ == "__main__":
    main()
