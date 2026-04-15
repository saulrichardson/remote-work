# Remote Work Startups

This repository owns the empirical pipeline for the `main/` codebase. The
Dropbox/Overleaf manuscript is downstream of this repo, not the other way
around.

The repo is organized around three phases:

1. `data`
   - upstream builders in [`src/py/`](src/py/) and [`src/stata/`](src/stata/)
   - outputs canonical datasets in [`data/clean/`](data/clean/)
2. `specs`
   - empirical Stata scripts in [`spec/stata/`](spec/stata/)
   - outputs machine-readable regressions and event-study exports in
     [`results/raw/`](results/raw/)
3. `paper`
   - paper-facing Python builders in [`writeup/py/`](writeup/py/)
   - outputs cleaned LaTeX tables and manuscript figures in
     [`results/cleaned/`](results/cleaned/)

That is the intended local contract:

- source-boundary inputs and accepted local boundaries
- canonical cleaned datasets
- empirical exports
- final paper assets

## What is in scope

This repo is the source of truth for:

- canonical cleaned datasets used by the active paper lane
- active empirical Stata specs
- active Python table and figure builders
- active raw empirical outputs in `results/raw/`
- active cleaned paper outputs in `results/cleaned/`
- generated lineage docs for the repo-owned `main.tex` asset lane

This repo is not the source of truth for:

- the full Overleaf manuscript source
- arbitrary Dropbox-only artifacts
- external manuscript figures still read from Overleaf `../Figures/...`
- manuscript assets whose generator has not been recovered in this repo

The active exclusions are documented explicitly in:

- [`docs/main_tex_assets.md`](docs/main_tex_assets.md)
- [`docs/paper_table_lineage.md`](docs/paper_table_lineage.md)
- [`docs/figure_lineage.md`](docs/figure_lineage.md)

## Run From Repo Root

All commands below assume you are in:

```bash
cd "/Users/saulrichardson/Dropbox/Remote Work Startups/main"
```

## Environment Setup

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install binsreg
```

Use the repo runtime wrapper for active Python builders:

```bash
./bin/project-python src/py/build_user_location_lookup.py
```

That wrapper gives the active Python surface one consistent import contract.

### Stata

Use the repo wrapper:

```bash
./bin/stata -q
```

`bin/stata` will:

- use `STATA_BIN` if set
- otherwise search common macOS Stata install locations
- otherwise fall back to `stata-se`, `stata-mp`, or `stata` on `PATH`

Required Stata packages for the active paper lane:

```stata
ssc install reghdfe, replace
ssc install ivreghdfe, replace
ssc install egenmore, replace
```

## Public Build Surface

The public `Makefile` surface mirrors the repo ontology directly:

```bash
make data
make specs
make paper
```

### `make data`

Runs the local upstream data-construction layer in dependency order.

It covers:

- lookup and geography helpers in [`src/py/`](src/py/)
- local Stata panel builders in [`src/stata/`](src/stata/)
- user, vacancy, Crunchbase, and deterministic postings-equity builders

It writes:

- canonical datasets in [`data/clean/`](data/clean/)
- deterministic upstream equity artifacts in
  [`results/raw/postings_description_equity/`](results/raw/postings_description_equity/)

The default local `data` contract intentionally starts from accepted boundaries
rather than rebuilding every heavy upstream artifact on this machine.

Accepted heavy local boundaries:

- [`data/clean/company_top_msa_by_half.csv`](data/clean/company_top_msa_by_half.csv)
- [`data/clean/modal_role_per_firm.dta`](data/clean/modal_role_per_firm.dta)
- [`data/clean/scoop_firm_tele_2.dta`](data/clean/scoop_firm_tele_2.dta)
- [`data/clean/eng_noneng_growth.csv`](data/clean/eng_noneng_growth.csv)
- [`data/clean/firm_geography_counts_imputed.csv`](data/clean/firm_geography_counts_imputed.csv)

Accepted manual external boundary:

- the OpenAI Batch download/merge path in the postings-equity workflow

That manual branch is documented in:

- [`docs/postings_equity_workflow.md`](docs/postings_equity_workflow.md)

### `make specs`

Runs the active empirical Stata lane in paper order.

It does two things:

1. regenerates the asset-contract-derived docs and preview input map
2. runs the active table-side and figure-side Stata specs under
   [`spec/stata/`](spec/stata/)

It writes:

- paper-facing machine-readable outputs under [`results/raw/`](results/raw/)
- spec logs under [`log/`](log/) and [`log/batch/`](log/batch/)

### `make paper`

Runs the paper-facing Python builders under [`writeup/py/`](writeup/py/).

It also regenerates the contract-derived docs, then renders:

- cleaned LaTeX fragments under [`results/cleaned/tex/`](results/cleaned/tex/)
- cleaned figures under [`results/cleaned/figures/`](results/cleaned/figures/)
- cleaned IRF panels under
  [`results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/`](results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/)

There are two valid paper-builder modes:

- descriptive assets:
  - `data/clean/` -> `writeup/py/` -> `results/cleaned/`
- estimation-driven assets:
  - `data/clean/` -> `spec/stata/` -> `results/raw/` -> `writeup/py/` -> `results/cleaned/`

`results/raw/` is the empirical-spec output layer, not the raw-data layer.

## The Pipeline In One View

### Upstream data construction

Canonical source-boundary inputs come from:

- [`data/raw/`](data/raw/)
- a small set of inherited source-boundary datasets that still live under
  [`data/clean/`](data/clean/)

Active builders then produce:

- `firm_panel.dta`
- `user_panel_precovid.dta`
- `user_attributes.dta`
- `user_hire_event_panel_precovid.dta`
- `firm_halfyear_panel_MERGED_POST.csv`
- `firm_panel_with_cb.csv`
- `firm_panel_with_cb_funding.csv`
- `csa_msa_top14_mapping.csv`
- and related canonical intermediates

The full upstream ontology is documented in:

- [`docs/local_runbook.md`](docs/local_runbook.md)
- [`docs/upstream_data_ontology.md`](docs/upstream_data_ontology.md)

### Empirical specifications

The core empirical work lives in [`spec/stata/`](spec/stata/).

The main active families are:

- user-productivity OLS and IV tables
- firm-scaling OLS and IV tables, including vacancy outcomes
- event-study figures for user and firm outcomes
- Crunchbase fundraising event-study and table family
- startup-cutoff bars
- engineer / non-engineer IRFs
- remote-hire event-study figure

The empirical overview is documented in:

- [`docs/core_specs.md`](docs/core_specs.md)

### Final paper assets

The repo-owned manuscript lane is defined by:

- [`writeup/py/paper_support/paper_asset_contract.json`](writeup/py/paper_support/paper_asset_contract.json)

Generated documentation from that contract:

- [`docs/main_tex_assets.md`](docs/main_tex_assets.md)
- [`docs/paper_table_lineage.md`](docs/paper_table_lineage.md)
- [`docs/figure_lineage.md`](docs/figure_lineage.md)

Those files tell you, asset by asset:

- what `main.tex` reads
- which Stata spec owns the raw export, if any
- which Python builder renders the final output
- which upstream datasets feed that asset

## Most Important Docs

If you are trying to understand the repo from scratch, read these in order:

1. [`docs/local_runbook.md`](docs/local_runbook.md)
   - exact run order, commands, accepted local boundaries, and output locations
2. [`docs/upstream_data_ontology.md`](docs/upstream_data_ontology.md)
   - detailed map of source-boundary inputs and generated datasets
3. [`docs/core_specs.md`](docs/core_specs.md)
   - high-level empirical designs behind the active specs
4. [`docs/main_tex_assets.md`](docs/main_tex_assets.md)
   - active manuscript asset inventory and exclusions
5. [`docs/paper_table_lineage.md`](docs/paper_table_lineage.md)
   - table-by-table lineage
6. [`docs/figure_lineage.md`](docs/figure_lineage.md)
   - figure-by-figure lineage

## Active Tree Map

- [`src/py/`](src/py/)
  - active Python upstream builders
- [`src/stata/`](src/stata/)
  - active Stata upstream builders
- [`spec/stata/`](spec/stata/)
  - active empirical Stata specs
- [`writeup/py/`](writeup/py/)
  - active paper-facing builders
- [`data/`](data/)
  - source-boundary inputs and canonical cleaned datasets
- [`results/`](results/)
  - raw empirical outputs and cleaned paper assets
- [`docs/`](docs/)
  - runbooks, empirical overview, lineage docs

Archive material was preserved under:

- [`src/archive/`](src/archive/)
- [`spec/archive/stata/`](spec/archive/stata/)
- [`writeup/archive/`](writeup/archive/)
- [`results/archive/`](results/archive/)

## Related Docs

- [`data/README.md`](data/README.md)
- [`results/README.md`](results/README.md)
- [`src/py/README.md`](src/py/README.md)
- [`src/stata/README.md`](src/stata/README.md)
- [`spec/stata/README.md`](spec/stata/README.md)
- [`writeup/py/README.md`](writeup/py/README.md)
