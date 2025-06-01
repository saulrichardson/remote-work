# WFH Startups — Repository Overview

This repository holds the full data pipeline and write-up for the paper *“Working-from-Home Start-ups”*.  The project is organised as a **linear workflow** – raw data enter at the top, a series of scripts transform them, and the final paper is compiled from the generated artefacts.

## Directory structure

| Folder | Purpose |
|--------|---------|
| `data/` | External inputs.  Raw files live in `data/raw`, processed panels in `data/processed`, and tiny illustrative samples (kept under version-control) in `data/samples`. |
| `src/` | Stata build scripts that turn the raw inputs into analysis-ready datasets.  Each script sources `src/globals.do` for unified paths and writes its output to `data/processed`. |
| `spec/` | Self-contained empirical specifications.  Every `.do` file loads the processed panels, runs a model, and exports both tidy tables and raw diagnostics into `results/`. |
| `py/` | Small Python utilities that post-process Stata outputs: merge standard errors, generate figures, and tidy tables before they reach the paper. |
| `results/` | Generated artefacts from all estimation scripts.  Split into `raw/`, `cleaned/`, and `figures/`.  Clean tables are later copied into `writeup/`. |
| `writeup/` | Contains the LaTeX source of the paper together with a `Makefile`.  The build rules collect cleaned tables from `results/cleaned` and compile the final PDF. |

```
data/raw  ─▶ src/ ─▶ data/processed ─▶ spec/ ─▶ results/ ─▶ py/ ─▶ writeup/
```

Each stage depends only on the outputs of the previous one.  Re-running a step therefore updates every downstream artefact without touching unrelated parts of the project.

## Building the paper

```
cd writeup
make            # Re-generates tables + figures and compiles consolidated-report.pdf
```

The `deploy` target of the same `Makefile` copies the freshly compiled PDF and cleaned tables into an Overleaf-synchronised Dropbox folder.

---

*Last updated: 2025-06-01*
