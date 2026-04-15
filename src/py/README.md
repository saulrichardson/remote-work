# `src/py/`

This directory holds the active Python upstream builders for the current
repo-owned paper lane.

Its job is specific:

- read source-boundary inputs from [`../../data/raw/`](../../data/raw/)
- read accepted inherited or heavy local boundaries where documented
- write canonical datasets to [`../../data/clean/`](../../data/clean/)
- write reusable machine-readable upstream branches where the active paper lane
  genuinely needs them

It is not the home for:

- empirical Stata specs
- final manuscript tables
- final manuscript figures
- historical sweep runners
- legacy exploratory builders

## Runtime Contract

Run active Python builders through:

```bash
./bin/project-python src/py/<script>.py
```

The canonical grouped entrypoint is:

```bash
make data
```

## Builder Families

### Lookup and geography helpers

- [`build_user_location_lookup.py`](build_user_location_lookup.py)
  - reads `data/raw/User_location.csv` plus city/CBSA lookup tables
  - writes `data/clean/user_location_lookup.csv`
- [`build_csa_msa_top14_mapping.py`](build_csa_msa_top14_mapping.py)
  - reads `data/raw/paper_aux/csa_top14_definition.csv`
  - writes `data/clean/csa_msa_top14_mapping.csv`

### User-side enrichments

- [`build_user_attributes.py`](build_user_attributes.py)
  - writes `data/clean/user_attributes.csv` and `data/clean/user_attributes.dta`
- [`build_remote_hire_event_panel.py`](build_remote_hire_event_panel.py)
  - writes `data/clean/user_hire_event_panel_precovid.dta`

### Vacancy branch

- [`build_vacancy_halfyear_panel.py`](build_vacancy_halfyear_panel.py)
  - writes `data/clean/vacancy/firm_halfyear_panel.csv`
- [`build_vacancy_outcomes_panel.py`](build_vacancy_outcomes_panel.py)
  - writes `data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv`

### Crunchbase branch

- [`build_crunchbase_crosswalk.py`](build_crunchbase_crosswalk.py)
  - writes `data/clean/crunchbase_crosswalk.csv`
- [`build_firm_panel_with_crunchbase.py`](build_firm_panel_with_crunchbase.py)
  - writes `data/clean/firm_panel_with_cb.csv`
- [`build_firm_panel_with_crunchbase_funding.py`](build_firm_panel_with_crunchbase_funding.py)
  - writes `data/clean/firm_panel_with_cb_funding.csv`

### Heavy but still active builders

These remain source-of-truth builders but are not part of the default local
`make data` contract:

- [`build_company_top_msa_by_half.py`](build_company_top_msa_by_half.py)
- [`build_engineer_nonengineer_growth.py`](build_engineer_nonengineer_growth.py)
- [`build_firm_geography_counts.py`](build_firm_geography_counts.py)

Their outputs are accepted heavy local boundaries in the default local flow.

### Postings-equity branch

- [`build_postings_equity_candidates.py`](build_postings_equity_candidates.py)
  - deterministic keyword-screened candidate export
- [`postings_equity_prompt_schema.py`](postings_equity_prompt_schema.py)
  - shared prompt and schema contract
- [`run_postings_equity_batch.py`](run_postings_equity_batch.py)
  - Batch API prepare / submit / poll / download tooling
- [`build_postings_equity_firm_merge.py`](build_postings_equity_firm_merge.py)
  - merges downloaded LLM outputs back to firm identifiers
- [`build_postings_equity_firm_halfyear_panel.py`](build_postings_equity_firm_halfyear_panel.py)
  - writes the firm-half-year equity panel consumed by the paper

This branch includes an accepted manual external boundary; see:

- [`../../docs/postings_equity_workflow.md`](../../docs/postings_equity_workflow.md)

## Design Rules

- one active builder should own one artifact or one tightly scoped transformation
- active names should describe the artifact produced
- fail loudly on missing or empty inputs
- upstream dataset construction belongs here, not in `spec/stata/`
- final manuscript assets do not belong here

## Useful Commands

Grouped local upstream run:

```bash
make data
```

Single-script examples:

```bash
./bin/project-python src/py/build_user_location_lookup.py
./bin/project-python src/py/build_user_attributes.py
./bin/project-python src/py/build_vacancy_halfyear_panel.py
./bin/project-python src/py/build_crunchbase_crosswalk.py
./bin/project-python src/py/build_postings_equity_candidates.py export
```

## Related Docs

- [`../../README.md`](../../README.md)
- [`../../docs/local_runbook.md`](../../docs/local_runbook.md)
- [`../../docs/upstream_data_ontology.md`](../../docs/upstream_data_ontology.md)
- [`../../docs/crunchbase_workflow.md`](../../docs/crunchbase_workflow.md)
- [`../../docs/postings_equity_workflow.md`](../../docs/postings_equity_workflow.md)
