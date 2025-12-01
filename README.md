# WFH Startups — Repository Guide

This repository contains the full data and writing pipeline for the remote‑work paper.  Everything is organised as a one‑way flow: external data land in `data/`, Stata builds the analytical panels, specifications export results into `results/`, Python scripts polish tables/figures, and the LaTeX sources in `writeup/` assemble the document.

Current mini-writeup PDF: [writeup/tex/final/mini-writeup.pdf](writeup/tex/final/mini-writeup.pdf).

```
data/raw  →  src/stata/  →  data/clean  →  spec/stata/  →  results/raw
                                       ↘
                                src/py/ (post-processing)  →  results/cleaned  →  writeup/
```

## Prerequisites

- **Stata 17+** (earlier versions should work if they support `reghdfe`).
- **Python 3.10+** with packages listed in `requirements.txt`.
- Optional: set the environment variable `PROJECT_ROOT` before running Stata/Python scripts when working outside the repo root (the bootstrap scripts will also auto-detect the root).

## Directory map

| Path | What lives here |
|------|-----------------|
| `data/raw/` | External sources (not tracked).  Place Scoop, Revelio, GitHub, etc. here. |
| `data/clean/` | Harmonised “clean” `.dta` panels produced by `src/stata/*.do`. |
| `data/samples/` | Tiny CSV snippets that ship with the repo for diagnostics. |
| `src/stata/` | Build scripts that construct the processed panels (`build_firm_panel.do`, `build_all_user_panels.do`, …). |
| `spec/stata/` | Empirical specifications. Each `.do` file reads the processed data, runs a model, and exports outputs into `results/raw/<specname>/`. |
| `src/py/` | Shared Python helpers (table formatters, figure generators, path utilities). |
| `results/raw/` | Direct exports from the Stata specs (CSV coefficient dumps, event-study series, etc.). |
| `results/cleaned/tex` & `results/cleaned/figures` | Paper-ready LaTeX tables and PNG figures created by the Python scripts. |
| `log/` | Run logs from bulk jobs (kept out of the tree root). |
| `docs/` | Research notes, auxiliary write-ups, and exploratory notebooks. |
| `writeup/` | LaTeX sources (`tex/`), spec-scoped Python formatters under `py/<spec>/`, scratch space, and the `Makefile` that rebuilds the paper. |

Generated artefacts live under `results/` and `writeup/tex/build/`; wipe them whenever you want to regenerate from scratch.

## Rebuilding the pipeline

1. **Prepare raw inputs**  
   - Drop all required raw files under `data/raw/` (they are not tracked by Git).  
   - The repository ships with metadata samples in `data/samples/` for quick sanity checks.

2. **Construct processed panels (Stata)**  
   Run the required build scripts from the repo root in Stata. Typical entry points:
   ```stata
   do src/stata/build_firm_panel.do          // firm-level panels and covariates
   do src/stata/build_all_user_panels.do     // user-level panels (multiple variants)
   do src/stata/build_firm_soc_panel_from_csv.do   // auxiliary firm data merges
   ```
Each script writes cleaned `.dta` files to `data/clean/` (with optional CSV mirrors to `data/samples/`).

3. **Run empirical specifications (Stata)**  
   Specifications live in `spec/stata/` and expect the processed panels from step 2.
   ```stata
   do spec/stata/user_productivity.do
   do spec/stata/user_productivity_initial.do
   do spec/stata/firm_scaling.do
   do spec/stata/user_mechanisms_with_growth.do
   do spec/stata/user_productivity_discrete_fr_focus.do
   do spec/stata/firm_scaling_vacancy_outcomes_htv2_95.do
   ```
   Outputs: coefficient tables, event-study series, and diagnostics under `results/raw/<specname>/`.

4. **Post-process tables & figures (Python)**  
   From `writeup/`, refresh all cleaned artefacts:
   ```bash
   cd writeup
   make mini-writeup-inputs   # runs the Python formatters/plotters
   ```
   This populates `results/cleaned/tex` and `results/cleaned/figures`.

5. **Compile the write-up (LaTeX)**  
   While still inside `writeup/`:
   ```bash
   make mini-writeup           # builds writeup/tex/final/mini-writeup.pdf
   ```
The Makefile also copies the curated tables/figures to the Overleaf-synced Dropbox folders configured at the top of the file.  
Python formatters now live under `writeup/py/user_productivity/`, `writeup/py/firm_scaling/`, and `writeup/py/startup_cutoff/`, mirroring the empirical specs so it is obvious which script produces each table or plot.

## How the main specs line up

| Spec | Purpose | Key outputs |
|------|---------|-------------|
| `spec/stata/user_productivity.do` | Baseline worker regressions (OLS + IV) | `results/raw/user_productivity_precovid/` |
| `spec/stata/user_productivity_initial.do` | No startup interaction baseline | `results/raw/user_productivity_initial_precovid/` |
| `spec/stata/firm_scaling.do` | Firm growth/join/leave regressions | `results/raw/firm_scaling/` |
| `spec/stata/firm_scaling_vacancy_outcomes_htv2_95.do` | Job-posting outcomes | `results/raw/firm_scaling_vacancy_outcomes_htv2_95/` |
| `spec/stata/user_mechanisms_with_growth.do` | Mechanism robustness checks | `results/raw/user_mechanisms_with_growth_precovid/` |
| `spec/stata/user_wage_fe_variants.do` | Wage regressions | `results/raw/user_wage_fe_variants_precovid/` |
| `spec/stata/user_productivity_discrete_fr_focus.do` | Fully remote vs hybrid comparisons | `results/raw/user_productivity_fr_focus_precovid_*` |
| `spec/stata/user_event_study_export.do` & `firm_event_study_export.do` | Event-study CSVs for plotting | `results/raw/user_event_study_precovid/`, `results/raw/firm_event_study/` |
| `spec/stata/user_event_study_fullrem_export.do` & `firm_event_study_fullrem_export.do` (plus vacancy variant) | Same event-study workflow but the treatment is a 0/1 fully-remote indicator | `results/raw/user_event_study_fullrem_*`, `results/raw/firm_event_study_fullrem/`, `results/raw/firm_vacancy_event_study_fullrem/` |

## Housekeeping & conventions

- **Logs and scratch work**  
  - `src/stata/log/` and `spec/stata/log/` capture Stata run logs; each directory sits alongside the scripts that generated those outputs.  
  - Use `spec/stata/scratch/`, `writeup/scratch/`, or `writeup/py/scratch/` for one-off experiments; move polished scripts back into the main folders.

- **Generated outputs**  
  - `results/` and `writeup/tex/build/` are derived artefacts—delete them to rerun the pipeline.  
  - Only the whitelisted tables/figures in `results/cleaned/` are synced to Overleaf.
- **Results lifecycle**
  - Stata specs export to `results/raw/<spec>/`.
  - Python formatters (writeup + shared helpers) emit publish-ready assets under `results/cleaned/`.
  - The mini-writeup, Overleaf sync, and any downstream consumers read exclusively from `results/cleaned/`.

- **Data handling**  
- Keep raw/cleaned data out of Git.  The repository assumes you can rebuild `data/clean/` using the supplied Stata scripts whenever needed.

- **Python helpers**  
  - `src/py/project_paths.py` resolves repo-relative paths and is imported by all Python scripts; it understands the `PROJECT_ROOT` environment variable as an override.

For questions about a particular module, open the corresponding folder (`spec/stata/` for empirical specs, `src/py/` for post-processing, `writeup/py/` for paper-specific formatting scripts).  Each script includes comments documenting required inputs and outputs.
