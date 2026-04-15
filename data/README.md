# Data Layout

This directory holds the upstream input and canonical dataset layers.

The intended flow is:

1. source-boundary files live under `data/raw/`
2. active builders in [`../src/py/`](../src/py/) and [`../src/stata/`](../src/stata/)
   construct canonical datasets under `data/clean/`
3. those canonical datasets feed either:
   - descriptive builders directly in [`../writeup/py/`](../writeup/py/)
   - or empirical specs first in [`../spec/stata/`](../spec/stata/)
4. final paper assets are written to [`../results/cleaned/`](../results/cleaned/)

## The Three Important Data Categories

### 1. `data/raw/`

This is the true raw/source-boundary layer.

Examples:

- vacancy postings
- postings-description shards
- Crunchbase CSVs
- raw worker-position exports
- raw education and location files

### 2. `data/clean/`

This is the canonical analysis-dataset layer.

The most important active datasets here are:

- `firm_panel.dta`
- `user_panel_precovid.dta`
- `user_attributes.dta`
- `user_hire_event_panel_precovid.dta`
- `crunchbase_crosswalk.csv`
- `firm_panel_with_cb.csv`
- `firm_panel_with_cb_funding.csv`
- `user_location_lookup.csv`
- `csa_msa_top14_mapping.csv`
- `company_top_msa_by_half.csv`
- `modal_role_per_firm.dta`
- `scoop_firm_tele_2.dta`
- `eng_noneng_growth.csv`
- `firm_geography_counts_imputed.csv`
- `vacancy/firm_halfyear_panel.csv`
- `vacancy/firm_halfyear_panel_MERGED_POST.csv`

### 3. Accepted source-boundary or heavy-boundary files that also live under `data/clean/`

Some files in `data/clean/` are not outputs of the local default rebuild
contract. They are accepted boundaries.

Inherited source-boundary datasets:

- `Contributions_Scoop.dta`
- `expanded_half_years_2.dta`
- `Firm_role_level.dta`
- `Scoop_Positions_Firm_Collapse2.csv`
- `gazetteer_cities.csv`
- `cbsa_city_lookup.csv`

Accepted heavy local boundaries:

- `company_top_msa_by_half.csv`
- `modal_role_per_firm.dta`
- `scoop_firm_tele_2.dta`
- `eng_noneng_growth.csv`
- `firm_geography_counts_imputed.csv`

## Local Build Contract

The public local upstream command is:

```bash
make data
```

That command rebuilds the local active upstream layer from:

- `data/raw/`
- inherited source-boundary datasets in `data/clean/`
- accepted heavy local boundaries in `data/clean/`
- the accepted manual postings-equity boundary in `results/raw/postings_description_equity/`

For the exact stage order, use:

- [`../docs/local_runbook.md`](../docs/local_runbook.md)
- [`../docs/upstream_data_ontology.md`](../docs/upstream_data_ontology.md)

## What Does Not Belong Here

- regression exports
- paper tables
- paper figures
- manuscript-facing LaTeX fragments

Those belong under [`../results/`](../results/), not under `data/`.

## Related Docs

- [`../README.md`](../README.md)
- [`../docs/local_runbook.md`](../docs/local_runbook.md)
- [`../docs/upstream_data_ontology.md`](../docs/upstream_data_ontology.md)
- [`../src/py/README.md`](../src/py/README.md)
- [`../src/stata/README.md`](../src/stata/README.md)
- [`../results/README.md`](../results/README.md)
