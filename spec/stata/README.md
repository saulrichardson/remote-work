# `spec/stata/`

This is the empirical estimation layer for the active repo-owned paper lane.

Its responsibilities are:

- read canonical datasets from [`../../data/clean/`](../../data/clean/)
- run the active paper-order regressions and event-study exports
- write machine-readable outputs to [`../../results/raw/`](../../results/raw/)
- write logs under [`../../log/`](../../log/) and [`../../log/batch/`](../../log/batch/)

It does not build final manuscript assets directly. That happens downstream in
[`../../writeup/py/`](../../writeup/py/).

## Active Structure

- [`_bootstrap.do`](_bootstrap.do)
  - compatibility shim to source [`../00_paths.do`](../00_paths.do)
- [`tables/`](tables/)
  - active table-side numbered specs
- [`figures/`](figures/)
  - active figure-side numbered specs

## Path Contract

The active Stata path surface is defined by:

- [`../00_paths.do`](../00_paths.do)
  - `$raw_data`
  - `$clean_data`
  - `$processed_data`
  - `$results`
  - `$LOG_DIR`

The execution chain is:

1. `make specs` calls [`../../bin/stata`](../../bin/stata) through the paper-lane helper
2. each spec sources [`_bootstrap.do`](_bootstrap.do)
3. `_bootstrap.do` sources [`../00_paths.do`](../00_paths.do)
4. the spec writes machine-readable outputs into `results/raw/...`

## Empirical Families

Table-side families:

- user-productivity OLS and IV
- firm-scaling OLS and IV
- vacancy outcomes extension
- Crunchbase fundraising tables
- user mechanisms and trait heterogeneity
- first-stage summary inputs

Figure-side families:

- user event-study
- firm event-study
- full-remote event-study variants
- startup-cutoff bars
- Crunchbase fundraising event-study
- engineer / non-engineer IRFs
- remote-hire event-study

For the higher-level empirical summary, see:

- [`../../docs/core_specs.md`](../../docs/core_specs.md)

## How To Run

Grouped public entrypoint:

```bash
make specs
```

Single-spec examples:

```bash
./bin/stata -b do spec/stata/tables/01_user_productivity_precovid_total_ols_single.do precovid
./bin/stata -b do spec/stata/tables/04_firm_scaling_precovid.do
./bin/stata -b do spec/stata/figures/01_user_event_study_precovid_ols.do precovid
```

## Output Interpretation

`results/raw/` is the empirical-export layer.

Typical outputs include:

- `consolidated_results.csv`
- event-study coefficient-path CSVs
- first-stage summary CSVs
- IRF `.dta` and `.csv` files

Those outputs are then rendered by the active Python paper builders in
[`../../writeup/py/`](../../writeup/py/).

## Related Docs

- [`tables/README.md`](tables/README.md)
- [`figures/README.md`](figures/README.md)
- [`../../docs/local_runbook.md`](../../docs/local_runbook.md)
- [`../../docs/core_specs.md`](../../docs/core_specs.md)
- [`../../docs/paper_table_lineage.md`](../../docs/paper_table_lineage.md)
- [`../../docs/figure_lineage.md`](../../docs/figure_lineage.md)
