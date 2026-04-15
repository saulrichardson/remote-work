# `writeup/py/`

This directory is the paper-facing rendering layer.

Its job is to turn canonical upstream inputs into final manuscript-facing
outputs under [`../../results/cleaned/`](../../results/cleaned/).

## Two Valid Input Modes

The active paper layer intentionally supports two different paths.

### 1. Descriptive builders

These builders read canonical cleaned datasets directly from
[`../../data/clean/`](../../data/clean/).

Current active examples:

- [`figures/01_firm_age_lt100_remote.py`](figures/01_firm_age_lt100_remote.py)
- [`figures/02_firm_teleworkable_remote.py`](figures/02_firm_teleworkable_remote.py)
- [`paper_support/table_of_means.py`](paper_support/table_of_means.py)

### 2. Estimation-driven builders

These builders read machine-readable Stata exports from
[`../../results/raw/`](../../results/raw/).

This is the dominant path for:

- user-productivity tables
- firm-scaling tables
- event-study figures
- startup-cutoff figures
- Crunchbase fundraising figure
- engineer / non-engineer IRFs
- remote-hire figure

## Active Output Surface

- `results/cleaned/tex/`
  - active cleaned LaTeX table fragments
- `results/cleaned/figures/`
  - active cleaned non-IRF figure outputs
- `results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/`
  - active cleaned IRF panels

## Active Families

- [`paper_support/`](paper_support/)
  - asset contract, contract-derived docs, and table-of-means support
- [`figures/`](figures/)
  - core descriptive figures and most figure builders
- [`firm_scaling/`](firm_scaling/)
  - firm-side table builders
- [`user_productivity/`](user_productivity/)
  - user-side table builders
- [`startup_cutoff/`](startup_cutoff/)
  - startup-cutoff figure builders
- [`user_hire/`](user_hire/)
  - remote-hire figure builder

## How To Run

Canonical grouped entrypoint:

```bash
make paper
```

Direct examples:

```bash
./bin/project-python writeup/py/figures/01_firm_age_lt100_remote.py
./bin/project-python writeup/py/figures/user_event_study_precovid_ols.py
./bin/project-python writeup/py/user_productivity/01_user_productivity_precovid_total_ols_single.py
```

## Design Rules

- one builder should own one paper asset or one tightly bounded asset family
- active builders should assume the project runtime contract from
  `./bin/project-python`
- no active builder should mutate `sys.path`
- descriptive builders are allowed to read `data/clean/` directly
- estimation-driven builders should read `results/raw/`

## Related Docs

- [`../../README.md`](../../README.md)
- [`../../docs/local_runbook.md`](../../docs/local_runbook.md)
- [`../../docs/main_tex_assets.md`](../../docs/main_tex_assets.md)
- [`../../docs/paper_table_lineage.md`](../../docs/paper_table_lineage.md)
- [`../../docs/figure_lineage.md`](../../docs/figure_lineage.md)
