# Codex Agent Onboarding

Use this checklist to get up to speed fast whenever you drop into the repo.

## 1. Repo Anatomy
- Read `README.md` first; it diagrams the one-way flow: `data/raw → src/stata → data/clean → spec/stata → results/raw → results/cleaned → writeup/`.
- All Stata build scripts live in `src/stata/`, specs/regressions in `spec/stata/`, shared Python helpers in `src/py/`, and LaTeX + writeup automation under `writeup/`.
- Generated artefacts are confined to `results/` and `writeup/tex/build/`; safe to delete/regenerate as needed.

## 2. Canonical Regressions
- `spec/stata/user_productivity.do` and `spec/stata/firm_scaling.do` are the core specs; they both bootstrap paths via `spec/stata/_bootstrap.do`, read the processed panels, run OLS + IV with `reghdfe/ivreghdfe`, and export CSVs into `results/raw/<specname>/`.
- Other `.do` files mirror this structure (variant arguments + consolidated result exports); search `spec/stata/` when you need robustness or event-study variants.

## 3. Building Data
- Raw inputs belong in `data/raw/` (not tracked). Stata builders in `src/stata/` create the cleaned `.dta` panels inside `data/clean/` (exposed via the `clean_data` global).
- Typical entry points: `do src/stata/build_firm_panel.do`, `do src/stata/build_all_user_panels.do`, plus any auxiliary merges (read README’s “Construct processed panels” section).

## 4. Post-Processing & Writeup
- Always follow the existing Makefile workflow when formatting results: run `make mini-writeup-inputs` (or `mini-writeup`) so the curated Python scripts regenerate tables/figures before syncing the whitelisted artefacts to Overleaf.
- LaTeX sources live in `writeup/tex/`; use the Makefile targets to compile into `writeup/tex/build/` and copy final PDFs to Dropbox. When experimenting with new numbers, compile them in a separate scratch document under `writeup/tex/` until they are final, then merge into the main mini-writeup.

## 5. Path Bootstrapping
- Every Stata spec should include `spec/stata/_bootstrap.do` before referencing `$processed_data` or `$results`. It autodetects `PROJECT_ROOT` (or respects the environment variable) so scripts run from anywhere.
- Python scripts rely on `src/py/project_paths.py` for the same purpose; import it instead of hardcoding paths.

## 6. Tips for Future Agents
- Prefer `rg` for code/data searches (`rg pattern spec/stata`).
- Never clean or reset unrelated files; the repo may be in a dirty state intentionally.
- When touching regression logic, mirror the existing `postfile … export delimited` structure so downstream formatters stay compatible.
- Use the Makefile targets instead of hand-running long chains of Python/LaTeX commands; they also handle Dropbox syncing.

## 7. Implementation Notes
- Never implement backwards functionality or branching logic; focus on minimal changes that satisfy the desired operating model (ask when unclear).
- Remember that the base specification is `spec/stata/user_productivity.do` and `spec/stata/firm_scaling.do`; downstream analyses must be consistent with those models.
- Use the available Stata CLI to run `.do` files, read the generated logs, and iterate until the empirical specification is coherent and reproducible.
- Large files are common—prefer Python pipelines (with DuckDB when needed) for heavy preprocessing before pushing data back into Stata.
