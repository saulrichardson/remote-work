# Handoff Memo: Active Paper-Lane Cleanup

Date: 2026-03-31

## Goal

The goal is to make the repo-owned empirical pipeline for the current Overleaf `main.tex`
clean, legible, and replication-ready.

Concretely, the intended structure is:

- `src/py/` and `src/stata/`
  - upstream dataset preparation only
- `spec/stata/`
  - empirical analysis only
- `writeup/py/`
  - paper-facing table and figure generation only
- `results/raw/`
  - raw machine-readable regression/export outputs
- `results/cleaned/`
  - only the active repo-owned `main.tex` tables and figures

The user’s design intent is stronger than “clean folders”:

- the empirical specification for an active paper asset should live in the active numbered
  Stata script itself
- active numbered scripts should not just delegate empirical work to other `.do` files
- multiple files per asset are acceptable only if they are narrowly scoped and clearly defined
- broad old scripts should be preserved in archive, not deleted

For now, the user explicitly said not to worry about:

- `Final.tex`
- the external JPG figures under Overleaf `../Figures/...`

## Current active scope

Grounded in the current Overleaf manuscript:

- active `../Results/Tables/...` assets: `19`
- active repo-owned `../Results/Figures/...` assets: `20`
- active external `../Figures/...` assets: `4`

Source-of-truth mapping docs:

- `docs/main_tex_assets.md`
- `docs/paper_table_lineage.md`
- `docs/figure_lineage.md`

## What has already been cleaned successfully

### Repo structure

- `spec/stata/` top level now contains only the active numbered paper scripts, `_bootstrap.do`,
  `README.md`, and `support/`
- non-paper Stata work was moved to `spec/archive/stata/`
- `src/py/` was narrowed to active upstream dataset builders only
- `src/stata/` was narrowed to active upstream Stata data builders only
- non-paper source-side work was moved to `src/archive/`
- `writeup/py/` was narrowed to active paper-facing builders only
- non-paper or historical writeup-side code was moved to `writeup/archive/`
- `results/raw/` now contains only active paper-lane raw branches
- non-paper raw branches and diagnostics were moved to `results/archive/`
- `results/cleaned/` now contains only the active paper-lane outputs:
  - `results/cleaned/tex/`: exactly `19` active table fragments
  - `results/cleaned/figures/`: exactly `18` active non-IRF figures
  - `results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/`:
    - `panelB_fullremote_engineer.png`
    - `panelB_fullremote_nonengineer.png`
    - `remote1/eng_noneng_irf_estimates.dta`
    - `remote1/eng_noneng_irf_results.csv`

### Logging and hygiene

- root `*.log` count: `0`
- top-level `spec/stata/*.log` count: `0`
- top-level `src/stata/*.log` count: `0`
- active `__pycache__` directories under `src/py` and `writeup/py` were removed

### Documentation

The following active runbooks were updated:

- `README.md`
- `data/README.md`
- `results/README.md`
- `results/archive/README.md`
- `src/py/README.md`
- `src/stata/README.md`
- `spec/stata/README.md`
- `spec/stata/support/README.md`
- `writeup/py/README.md`
- `writeup/py/figures/README.md`
- `writeup/py/firm_scaling/README.md`
- `writeup/py/user_productivity/README.md`
- `writeup/py/startup_cutoff/README.md`
- `writeup/py/user_hire/README.md`
- `docs/README.md`
- `docs/main_tex_assets.md`
- `docs/paper_table_lineage.md`
- `docs/figure_lineage.md`
- `docs/crunchbase_workflow.md`

### Upstream Crunchbase lineage

The missing explicit builder for the firm-to-Crunchbase merge was added:

- `src/py/build_firm_panel_with_crunchbase.py`

This now makes the Crunchbase upstream path explicit:

1. `build_crunchbase_crosswalk.py`
2. `build_firm_panel_with_crunchbase.py`
3. `build_firm_panel_with_crunchbase_funding.py`

## What has been rerun and verified

### Tables

The active paper table lane was rerun from the cleaned active surface.

Verified result:

- active tables matching Overleaf byte-for-byte: `19 / 19`

### Build preview

The local preview still compiles successfully:

- `writeup/build/main_assets_preview/main_assets_preview.pdf`

### Figures

The active figure scripts rerun successfully from the cleaned active surface.

However, the figure parity result is mixed:

- active figure scripts run: yes
- active figure lineage mapped: yes
- active figures pixel-identical to current Overleaf copies: `3 / 20`

The three current pixel-identical figure outputs are:

- `startup_cutoff_bars_total_contributions_q100.png`
- `startup_cutoff_bars_growth_rate_we.png`
- `user_hire_event_study_remote_rank_mw.png`

So the figure lane is structurally clean and runnable, but not yet visually reconciled to the
current Overleaf copies.

## Main remaining problem

The biggest remaining mismatch with the user’s goal is in `spec/stata/`.

The current active numbered scripts are still too wrapper-like. Many of them call support scripts
for the actual empirical work.

This is the core issue the next agent should focus on.

Examples:

- `spec/stata/01_user_productivity_precovid_total_ols_single.do`
  - calls:
    - `spec/stata/support/run_user_productivity_initial_single_scope.do`
    - `spec/stata/support/run_user_productivity_altfe_single_scope.do`

- `spec/stata/03_startup_cutoff_bars_total_contributions_q100.do`
  - calls:
    - `spec/stata/support/user_productivity_startup_cutoff_sweep.do`
    - `spec/stata/support/firm_scaling_startup_cutoff_sweep.do`

- `spec/stata/16_panelB_fullremote_engineer.do`
  - calls:
    - `spec/stata/support/user_irfs_eng_noneng_remote_fast.do`

Grounded count:

- active numbered Stata scripts still delegating empirical work to support `.do` files: `25`

The user explicitly does not want that end state. The active empirical logic should be in the
numbered script itself, with only minimal bootstrap/path infrastructure shared.

## Work remaining

### 1. Inline empirical logic out of `spec/stata/support/`

This is the highest-priority remaining task.

Target:

- keep `_bootstrap.do` as infrastructure if needed
- move the actual empirical code from `spec/stata/support/*.do` into the numbered scripts in
  `spec/stata/`
- once verified, archive the old support scripts that are no longer needed

Recommended refactor order:

1. user productivity core
   - `06`
   - `07`
   - `34`
   - `35`

2. firm scaling core
   - `09`

3. top-metro and filter families
   - `14`
   - `16`

4. startup-cutoff families
   - `17`
   - `18`

5. event-study exporters
   - `03`
   - `04`
   - `19` to `29`
   - `32`

6. IRF exporters
   - `30`
   - `31`

Important constraint:

- do not change the empirical specification itself
- copy or inline the minimum logic necessary
- rerun after each family and compare outputs

### 2. Reconcile active figures to the current Overleaf copies

The figure problem is no longer missing lineage. It is render/style mismatch.

The next agent should do a family-by-family figure reconciliation, starting with:

- `writeup/py/plot_event_study.py`
- `writeup/py/figures/build_core_figures.py`
- `writeup/py/figures/plot_user_irfs_eng_noneng_remote.py`

The active scripts already run. The task is to understand why the rendered PNGs differ from the
current Overleaf versions and bring them into alignment without changing the underlying
regressions.

### 3. Keep documentation synchronized with the refactor

As the support-layer inlining happens, the following docs will need updating:

- `spec/stata/README.md`
- `spec/stata/support/README.md`
- `docs/paper_table_lineage.md`
- `docs/figure_lineage.md`
- `docs/main_tex_assets.md`
- `README.md`

## What the next agent should not spend time on right now

- do not worry about `Final.tex`
- do not worry about the external JPG figures under Overleaf `../Figures/...`
- do not redesign the Makefile around dynamic discovery
- do not broaden the scope beyond the active repo-owned `main.tex` lane

## Suggested next move

The best next step is:

1. pick one numbered Stata family, starting with `06` and `07`
2. inline the empirical logic from `spec/stata/support/` into those files
3. rerun those assets and verify raw outputs and final table fragments still match
4. repeat family by family

That is the main remaining path from “clean and runnable” to the user’s actual target state.
