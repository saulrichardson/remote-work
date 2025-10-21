# WFH Startups — Repository Overview

This repository holds the full data pipeline and write-up for the paper *“Working-from-Home Start-ups”*.  The project is organised as a **linear workflow** – raw data enter at the top, a series of scripts transform them, and the final paper is compiled from the generated artefacts.

## Directory structure

| Folder | Purpose |
|--------|---------|
| `data/` | External inputs.  Raw files live in `data/raw`, processed panels in `data/processed`, and tiny illustrative samples (kept under version-control) in `data/samples`. |
| `src/` | Stata build scripts that turn the raw inputs into analysis-ready datasets.  Each script sources `src/globals.do` for unified paths and writes its output to `data/processed`. |
| `spec/` | Self-contained empirical specifications.  Every `.do` file loads the processed panels, runs a model, and exports both tidy tables and raw diagnostics into `results/`. |
| `scripts/` | Python utilities that post-process Stata outputs: merge standard errors, generate figures, and tidy tables before they reach the paper. |
| `results/` | Generated artefacts from all estimation scripts.  Split into `raw/`, `cleaned/`, and `figures/`.  Clean tables are later copied into `writeup/`. |
| `writeup/` | Contains the LaTeX source of the paper together with a `Makefile`.  The build rules collect cleaned tables from `results/cleaned` and compile the final PDF. |

```
data/raw  ─▶ src/ ─▶ data/processed ─▶ spec/ ─▶ results/ ─▶ scripts/ ─▶ writeup/
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

## Housekeeping rules

- Drop every Stata log (and other runtime artefacts) into `log/` or `spec/log/`. The root of the repository should only contain source files and the primary directory skeleton.
- Treat `spec/scratch/` and `writeup/scratch/` as sandboxes for one-off investigations. Anything that graduates into the main pipeline should move back into `spec/` or `writeup/tex/`.
- `results/` is entirely generated. Only the small whitelist of tables and figures that feed the write-up stay version-controlled; everything else is ignored and can be blown away before regenerating.
- LaTeX intermediates live under `writeup/build/`, which is ignored. Only the sources under `writeup/tex/` and the curated PDFs under `writeup/final/` are expected to be tracked.
- Data inputs stay outside Git: use `data/raw/` and `data/processed/` locally, and rely on the documented pipeline scripts to rebuild them when needed.
