# Upstream Data Ontology

This document is the detailed map of the active upstream data-construction
layer.

Use it when you need to answer questions like:

- which inputs are true source boundaries
- which inputs are accepted heavy local boundaries
- which builders own which canonical datasets
- what `make data` really does
- which downstream empirical families depend on each upstream output

For the exact command sequence, see:

- [`local_runbook.md`](local_runbook.md)

## The Core Distinction

The repo intentionally separates four kinds of upstream inputs.

### 1. Raw source files under `data/raw/`

These are genuine source boundaries. They are not expected to be generated
inside this repo.

Representative examples:

- [`data/raw/Scoop_workers_positions.csv`](../data/raw/Scoop_workers_positions.csv)
- [`data/raw/Scoop_alt.csv`](../data/raw/Scoop_alt.csv)
- [`data/raw/Scoop_Linkedin.csv`](../data/raw/Scoop_Linkedin.csv)
- [`data/raw/Scoop_Education.csv`](../data/raw/Scoop_Education.csv)
- [`data/raw/User_location.csv`](../data/raw/User_location.csv)
- [`data/raw/vacancy/Postings_scoop.csv`](../data/raw/vacancy/Postings_scoop.csv)
- [`data/raw/postings_description/`](../data/raw/postings_description/)
- [`data/raw/crunchbase/organizations.csv`](../data/raw/crunchbase/organizations.csv)
- [`data/raw/crunchbase/funding_rounds.csv`](../data/raw/crunchbase/funding_rounds.csv)
- [`data/raw/paper_aux/csa_top14_definition.csv`](../data/raw/paper_aux/csa_top14_definition.csv)

### 2. Inherited source-boundary datasets that still live under `data/clean/`

These are not “missing builders.” They are historical source inputs that the
active local contract accepts as boundaries.

Examples:

- [`data/clean/Contributions_Scoop.dta`](../data/clean/Contributions_Scoop.dta)
- [`data/clean/expanded_half_years_2.dta`](../data/clean/expanded_half_years_2.dta)
- [`data/clean/Firm_role_level.dta`](../data/clean/Firm_role_level.dta)
- [`data/clean/Scoop_Positions_Firm_Collapse2.csv`](../data/clean/Scoop_Positions_Firm_Collapse2.csv)
- [`data/clean/gazetteer_cities.csv`](../data/clean/gazetteer_cities.csv)
- [`data/clean/cbsa_city_lookup.csv`](../data/clean/cbsa_city_lookup.csv)

### 3. Heavy upstream artifacts accepted as local boundaries

These files do have builders in the repo, but the builders are intentionally too
heavy for the default local `make data` contract.

Accepted heavy local boundaries:

- [`data/clean/company_top_msa_by_half.csv`](../data/clean/company_top_msa_by_half.csv)
- [`data/clean/modal_role_per_firm.dta`](../data/clean/modal_role_per_firm.dta)
- [`data/clean/scoop_firm_tele_2.dta`](../data/clean/scoop_firm_tele_2.dta)
- [`data/clean/eng_noneng_growth.csv`](../data/clean/eng_noneng_growth.csv)
- [`data/clean/firm_geography_counts_imputed.csv`](../data/clean/firm_geography_counts_imputed.csv)

Their source-of-truth builders still live in the repo:

- [`src/py/build_company_top_msa_by_half.py`](../src/py/build_company_top_msa_by_half.py)
- [`src/stata/build_firm_modal_role.do`](../src/stata/build_firm_modal_role.do)
- [`src/stata/build_firm_teleworkable_scores.do`](../src/stata/build_firm_teleworkable_scores.do)
- [`src/py/build_engineer_nonengineer_growth.py`](../src/py/build_engineer_nonengineer_growth.py)
- [`src/py/build_firm_geography_counts.py`](../src/py/build_firm_geography_counts.py)

### 4. Manual external-model boundary inside the data layer

The postings-description equity branch includes one accepted manual boundary:

- OpenAI Batch submission, polling, download, and posting-level merge

The key materialized local boundary file for the downstream pipeline is:

- [`results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv`](../results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv)

The full branch is documented in:

- [`postings_equity_workflow.md`](postings_equity_workflow.md)

## Downstream Handoff To The Paper Layer

The upstream layer documented here feeds the paper lane in two legitimate ways.

### Descriptive path

- canonical dataset in `data/clean/`
- direct paper-facing builder in [`writeup/py/`](../writeup/py/)
- final output in `results/cleaned/`

Examples:

- [`writeup/py/figures/01_firm_age_lt100_remote.py`](../writeup/py/figures/01_firm_age_lt100_remote.py)
- [`writeup/py/figures/02_firm_teleworkable_remote.py`](../writeup/py/figures/02_firm_teleworkable_remote.py)
- [`writeup/py/paper_support/table_of_means.py`](../writeup/py/paper_support/table_of_means.py)

### Estimation-driven path

- canonical dataset in `data/clean/`
- empirical Stata spec in [`spec/stata/`](../spec/stata/)
- machine-readable export in `results/raw/`
- final builder in [`writeup/py/`](../writeup/py/)
- final output in `results/cleaned/`

Example:

- [`spec/stata/figures/01_user_event_study_precovid_ols.do`](../spec/stata/figures/01_user_event_study_precovid_ols.do)
  -> [`results/raw/01_user_event_study_precovid_ols/`](../results/raw/01_user_event_study_precovid_ols/)
  -> [`writeup/py/figures/user_event_study_precovid_ols.py`](../writeup/py/figures/user_event_study_precovid_ols.py)

## What `make data` Covers

The local `data` phase covers deterministic active builders in dependency order.

### Stage 1. Lookup and classification helpers

- [`src/py/build_user_location_lookup.py`](../src/py/build_user_location_lookup.py)
  - reads raw user-location source plus city/CBSA reference files
  - writes [`data/clean/user_location_lookup.csv`](../data/clean/user_location_lookup.csv)
- [`src/py/build_csa_msa_top14_mapping.py`](../src/py/build_csa_msa_top14_mapping.py)
  - reads the recovered top-metro definition
  - writes [`data/clean/csa_msa_top14_mapping.csv`](../data/clean/csa_msa_top14_mapping.csv)

### Stage 2. Canonical Stata panels

- [`src/stata/build_firm_panel.do`](../src/stata/build_firm_panel.do)
  - reads raw firm-side inputs plus accepted local boundaries
  - writes [`data/clean/firm_panel.dta`](../data/clean/firm_panel.dta)
- [`src/stata/build_all_user_panels.do`](../src/stata/build_all_user_panels.do)
  - reads source-boundary user inputs plus accepted local boundaries
  - writes:
    - [`data/clean/user_panel_unbalanced.dta`](../data/clean/user_panel_unbalanced.dta)
    - [`data/clean/user_panel_balanced.dta`](../data/clean/user_panel_balanced.dta)
    - [`data/clean/user_panel_precovid.dta`](../data/clean/user_panel_precovid.dta)

### Stage 3. User-side enrichments

- [`src/py/build_user_attributes.py`](../src/py/build_user_attributes.py)
  - writes [`data/clean/user_attributes.csv`](../data/clean/user_attributes.csv) and
    [`data/clean/user_attributes.dta`](../data/clean/user_attributes.dta)
- [`src/py/build_remote_hire_event_panel.py`](../src/py/build_remote_hire_event_panel.py)
  - writes [`data/clean/user_hire_event_panel_precovid.dta`](../data/clean/user_hire_event_panel_precovid.dta)

### Stage 4. Vacancy branch

- [`src/py/build_vacancy_halfyear_panel.py`](../src/py/build_vacancy_halfyear_panel.py)
  - writes [`data/clean/vacancy/firm_halfyear_panel.csv`](../data/clean/vacancy/firm_halfyear_panel.csv)
- [`src/py/build_vacancy_outcomes_panel.py`](../src/py/build_vacancy_outcomes_panel.py)
  - writes [`data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv`](../data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv)

### Stage 5. Crunchbase branch

- [`src/py/build_crunchbase_crosswalk.py`](../src/py/build_crunchbase_crosswalk.py)
  - writes [`data/clean/crunchbase_crosswalk.csv`](../data/clean/crunchbase_crosswalk.csv)
- [`src/py/build_firm_panel_with_crunchbase.py`](../src/py/build_firm_panel_with_crunchbase.py)
  - writes [`data/clean/firm_panel_with_cb.csv`](../data/clean/firm_panel_with_cb.csv)
- [`src/py/build_firm_panel_with_crunchbase_funding.py`](../src/py/build_firm_panel_with_crunchbase_funding.py)
  - writes [`data/clean/firm_panel_with_cb_funding.csv`](../data/clean/firm_panel_with_cb_funding.csv)

### Stage 6. Postings-equity deterministic segment

- [`src/py/build_postings_equity_candidates.py`](../src/py/build_postings_equity_candidates.py)
  - writes [`results/raw/postings_description_equity/equity_candidates.parquet`](../results/raw/postings_description_equity/equity_candidates.parquet)
- [`src/py/build_postings_equity_firm_halfyear_panel.py`](../src/py/build_postings_equity_firm_halfyear_panel.py)
  - reads the materialized posting-level merge output from the accepted manual boundary
  - writes [`results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`](../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv)

## Canonical Datasets And Their Main Downstream Users

### `firm_panel.dta`

Built by:

- [`src/stata/build_firm_panel.do`](../src/stata/build_firm_panel.do)

Main downstream uses:

- firm-scaling tables and figures
- descriptive core firm figures
- table of means
- remote-hire and mechanisms downstream joins

### `user_panel_precovid.dta`

Built by:

- [`src/stata/build_all_user_panels.do`](../src/stata/build_all_user_panels.do)

Main downstream uses:

- user-productivity tables
- user event-study figures
- descriptive core firm figures
- table of means

### `user_attributes.dta`

Built by:

- [`src/py/build_user_attributes.py`](../src/py/build_user_attributes.py)

Main downstream uses:

- [`spec/stata/tables/09_user_productivity_traits_dual_precovid_ols.do`](../spec/stata/tables/09_user_productivity_traits_dual_precovid_ols.do)

### `user_hire_event_panel_precovid.dta`

Built by:

- [`src/py/build_remote_hire_event_panel.py`](../src/py/build_remote_hire_event_panel.py)

Main downstream uses:

- [`spec/stata/figures/18_user_hire_event_study_remote_rank_mw.do`](../spec/stata/figures/18_user_hire_event_study_remote_rank_mw.do)

### `firm_halfyear_panel_MERGED_POST.csv`

Built by:

- [`src/py/build_vacancy_outcomes_panel.py`](../src/py/build_vacancy_outcomes_panel.py)

Main downstream uses:

- [`spec/stata/tables/04_firm_scaling_precovid.do`](../spec/stata/tables/04_firm_scaling_precovid.do)
- vacancy event-study figure specs

### `firm_panel_with_cb_funding.csv`

Built by:

- [`src/py/build_firm_panel_with_crunchbase_funding.py`](../src/py/build_firm_panel_with_crunchbase_funding.py)

Main downstream uses:

- Crunchbase fundraising tables
- Crunchbase fundraising event-study figure

### `latest_firm_yh_llm_equity_enriched.csv`

Built by:

- [`src/py/build_postings_equity_firm_halfyear_panel.py`](../src/py/build_postings_equity_firm_halfyear_panel.py)

Main downstream uses:

- [`writeup/py/paper_support/table_of_means.py`](../writeup/py/paper_support/table_of_means.py)
- [`spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do`](../spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do)

## Related Docs

- [`local_runbook.md`](local_runbook.md)
- [`core_specs.md`](core_specs.md)
- [`../src/py/README.md`](../src/py/README.md)
- [`../src/stata/README.md`](../src/stata/README.md)
