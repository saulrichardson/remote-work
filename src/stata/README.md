# `src/stata/`

This directory is the Stata side of the upstream data-construction layer.

These files prepare canonical datasets upstream of the empirical specification
layer. They do not own final paper regressions.

## Active Builders

- [`build_firm_panel.do`](build_firm_panel.do)
  - writes [`data/clean/firm_panel.dta`](../../data/clean/firm_panel.dta)
- [`build_all_user_panels.do`](build_all_user_panels.do)
  - writes the canonical user-panel family under `data/clean/`
- [`build_firm_modal_role.do`](build_firm_modal_role.do)
  - writes [`data/clean/modal_role_per_firm.dta`](../../data/clean/modal_role_per_firm.dta)
  - remains active, but is an accepted heavy local boundary
- [`build_firm_teleworkable_scores.do`](build_firm_teleworkable_scores.do)
  - writes [`data/clean/scoop_firm_tele_2.dta`](../../data/clean/scoop_firm_tele_2.dta)
  - remains active, but is an accepted heavy local boundary

## What These Scripts Read

The upstream Stata layer mixes:

- raw source files from [`../../data/raw/`](../../data/raw/)
- inherited source-boundary datasets under [`../../data/clean/`](../../data/clean/)
- accepted heavy local boundaries under [`../../data/clean/`](../../data/clean/)

Important inherited source-boundary inputs:

- `Contributions_Scoop.dta`
- `expanded_half_years_2.dta`
- `Firm_role_level.dta`
- `Scoop_Positions_Firm_Collapse2.csv`

Important accepted heavy local boundaries:

- `modal_role_per_firm.dta`
- `scoop_firm_tele_2.dta`

## Relation To The Rest Of The Repo

`src/stata/` is upstream of both paper-output modes:

- descriptive assets:
  - `data/clean/` -> `writeup/py/`
- estimation-driven assets:
  - `data/clean/` -> `spec/stata/` -> `results/raw/` -> `writeup/py/`

This folder owns only the dataset-construction side of that split.

## How To Run

Canonical grouped entrypoint:

```bash
make data
```

Direct Stata reruns remain useful for debugging:

```bash
./bin/stata -b do src/stata/build_firm_panel.do
./bin/stata -b do src/stata/build_all_user_panels.do
```

The heavy builders are intentionally outside the default local `make data`
contract because they import the full worker-position source.

## Related Docs

- [`../../README.md`](../../README.md)
- [`../../docs/local_runbook.md`](../../docs/local_runbook.md)
- [`../../docs/upstream_data_ontology.md`](../../docs/upstream_data_ontology.md)
- [`../../spec/stata/README.md`](../../spec/stata/README.md)
