#!/usr/bin/env python3
"""
Generate a quick LaTeX table + PDF write-up for the firm wage scaling results.

Pipeline:
    1. Read ``results/raw/firm_scaling_wages/consolidated_results.csv``.
    2. Use the existing table formatter (``simple_table_from_consolidated``)
       to create ``results/cleaned/firm_scaling_wages.tex``.
    3. Write a lightweight LaTeX document that inputs the table and compile it
       with ``latexmk`` to ``tex/firm_scaling_wages_writeup.pdf``.

Run:
    python py/build_firm_scaling_wages_writeup.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CSV_PATH = ROOT / "results" / "raw" / "firm_scaling_wages" / "consolidated_results.csv"
DOC_DIR = ROOT / "tex"
DOC_PATH = DOC_DIR / "firm_scaling_wages_writeup.tex"
PDF_NAME = DOC_PATH.with_suffix(".pdf").name

CAPTION_TEMPLATE = "Firm wage regressions ({}; OLS and IV)"
LABEL_TEMPLATE = "tab:firm_scaling_wages_{}"


def slugify(name: str) -> str:
    """Simple slug for filesystem/labels."""

    return "".join(c for c in name.lower().replace(" ", "_") if c.isalnum() or c == "_")


def build_tables() -> list[tuple[str, Path]]:
    """Create one LaTeX table per outcome; return list of (outcome, path)."""

    import pandas as pd
    from simple_table_from_consolidated import build_table

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing regression output: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)
    outcomes = df["outcome"].unique()

    out_entries: list[tuple[str, Path]] = []
    out_dir = ROOT / "results" / "cleaned"
    out_dir.mkdir(parents=True, exist_ok=True)

    for outcome in outcomes:
        sub = df[df["outcome"] == outcome].copy()
        slug = slugify(outcome)
        caption = CAPTION_TEMPLATE.format(outcome.replace("_", " "))
        label = LABEL_TEMPLATE.format(slug)
        tex_table = build_table(sub, caption=caption, label=label)
        path = out_dir / f"firm_scaling_wages_{slug}.tex"
        path.write_text(tex_table)
        out_entries.append((outcome, path))

    return out_entries


def write_document(table_entries: list[tuple[str, Path]]) -> None:
    """Emit a minimal TeX document that inputs all regression tables."""

    DOC_DIR.mkdir(parents=True, exist_ok=True)

    blocks = []
    for outcome, path in table_entries:
        pretty = outcome.replace("_", " ")
        rel = path.relative_to(ROOT)
        blocks.append(
            rf"\subsection*{{Outcome: {pretty}}}" + "\n" +
            rf"\input{{../{rel}}}"
        )

    inputs = "\n\\medskip\n".join(blocks)

    doc = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath}
\usepackage{booktabs}
\usepackage{makecell}
\usepackage{dsfont}
\usepackage{float}
\usepackage{setspace}
\setstretch{1.15}

\title{Firm Scaling: Wage Outcomes}
\date{\today}
\author{}

\begin{document}
\maketitle

\section*{Regression Results}
\begin{small}
INPUT_BLOCK
\end{small}

\end{document}
"""

    DOC_PATH.write_text(doc.replace("INPUT_BLOCK", inputs), encoding="utf-8")


def compile_pdf() -> None:
    """Run latexmk to build the PDF inside the tex/ directory."""

    cmd = ["latexmk", "-pdf", DOC_PATH.name]
    subprocess.run(cmd, cwd=DOC_PATH.parent, check=True)


def main() -> None:
    table_paths = build_tables()
    write_document(table_paths)
    compile_pdf()
    print(f"✓ PDF written to tex/{PDF_NAME}")


if __name__ == "__main__":
    main()
