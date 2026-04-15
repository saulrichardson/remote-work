# Local Runbook

This is the operational runbook for the active repo-owned paper lane.

It answers four practical questions:

1. where to run commands from
2. what each public command does
3. which files are accepted boundaries for local runs
4. where outputs and logs land at each phase

## Run From Repo Root

All commands assume:

```bash
cd "/Users/saulrichardson/Dropbox/Remote Work Startups/main"
```

## Environment

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install binsreg
```

Use the repo wrapper for active Python scripts:

```bash
./bin/project-python src/py/build_user_location_lookup.py
```

### Stata

Check the repo wrapper:

```bash
./bin/stata -q
```

Required Stata packages:

```stata
ssc install reghdfe, replace
ssc install ivreghdfe, replace
ssc install egenmore, replace
```

## Public Commands

The public command surface is intentionally small:

```bash
make data
make specs
make paper
```

Run them in that order when you want a full local rebuild from accepted local
boundaries to final paper assets.

## Phase 1: `make data`

`make data` runs the local upstream construction layer.

### What it runs

The current order from [`Makefile`](../Makefile) is:

1. [`src/py/build_user_location_lookup.py`](../src/py/build_user_location_lookup.py)
2. [`src/py/build_csa_msa_top14_mapping.py`](../src/py/build_csa_msa_top14_mapping.py)
3. [`src/stata/build_firm_panel.do`](../src/stata/build_firm_panel.do)
4. [`src/stata/build_all_user_panels.do`](../src/stata/build_all_user_panels.do)
5. [`src/py/build_user_attributes.py`](../src/py/build_user_attributes.py)
6. [`src/py/build_remote_hire_event_panel.py`](../src/py/build_remote_hire_event_panel.py)
7. [`src/py/build_vacancy_halfyear_panel.py`](../src/py/build_vacancy_halfyear_panel.py)
8. [`src/py/build_vacancy_outcomes_panel.py`](../src/py/build_vacancy_outcomes_panel.py)
9. [`src/py/build_crunchbase_crosswalk.py`](../src/py/build_crunchbase_crosswalk.py)
10. [`src/py/build_firm_panel_with_crunchbase.py`](../src/py/build_firm_panel_with_crunchbase.py)
11. [`src/py/build_firm_panel_with_crunchbase_funding.py`](../src/py/build_firm_panel_with_crunchbase_funding.py)
12. [`src/py/build_postings_equity_candidates.py`](../src/py/build_postings_equity_candidates.py) `export`
13. [`src/py/build_postings_equity_firm_halfyear_panel.py`](../src/py/build_postings_equity_firm_halfyear_panel.py)

### What it writes

Representative outputs:

- [`data/clean/user_location_lookup.csv`](../data/clean/user_location_lookup.csv)
- [`data/clean/csa_msa_top14_mapping.csv`](../data/clean/csa_msa_top14_mapping.csv)
- [`data/clean/firm_panel.dta`](../data/clean/firm_panel.dta)
- [`data/clean/user_panel_precovid.dta`](../data/clean/user_panel_precovid.dta)
- [`data/clean/user_attributes.dta`](../data/clean/user_attributes.dta)
- [`data/clean/user_hire_event_panel_precovid.dta`](../data/clean/user_hire_event_panel_precovid.dta)
- [`data/clean/vacancy/firm_halfyear_panel.csv`](../data/clean/vacancy/firm_halfyear_panel.csv)
- [`data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv`](../data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv)
- [`data/clean/crunchbase_crosswalk.csv`](../data/clean/crunchbase_crosswalk.csv)
- [`data/clean/firm_panel_with_cb.csv`](../data/clean/firm_panel_with_cb.csv)
- [`data/clean/firm_panel_with_cb_funding.csv`](../data/clean/firm_panel_with_cb_funding.csv)
- [`results/raw/postings_description_equity/equity_candidates.parquet`](../results/raw/postings_description_equity/equity_candidates.parquet)
- [`results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`](../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv)

### Accepted local boundaries

The local `data` contract does not attempt to rebuild every heavy upstream step
from ultimate raw origin on this machine.

Accepted heavy local boundaries:

- [`data/clean/company_top_msa_by_half.csv`](../data/clean/company_top_msa_by_half.csv)
- [`data/clean/modal_role_per_firm.dta`](../data/clean/modal_role_per_firm.dta)
- [`data/clean/scoop_firm_tele_2.dta`](../data/clean/scoop_firm_tele_2.dta)
- [`data/clean/eng_noneng_growth.csv`](../data/clean/eng_noneng_growth.csv)
- [`data/clean/firm_geography_counts_imputed.csv`](../data/clean/firm_geography_counts_imputed.csv)

Those files do have builders in the repo, but the builders are intentionally
too heavy for the default local contract:

- [`src/py/build_company_top_msa_by_half.py`](../src/py/build_company_top_msa_by_half.py)
- [`src/stata/build_firm_modal_role.do`](../src/stata/build_firm_modal_role.do)
- [`src/stata/build_firm_teleworkable_scores.do`](../src/stata/build_firm_teleworkable_scores.do)
- [`src/py/build_engineer_nonengineer_growth.py`](../src/py/build_engineer_nonengineer_growth.py)
- [`src/py/build_firm_geography_counts.py`](../src/py/build_firm_geography_counts.py)

### Accepted manual boundary

The postings-equity branch has one explicit manual boundary:

- OpenAI Batch submission, polling, download, and posting-level merge

For local runs, the relevant materialized boundary file is:

- [`results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv`](../results/raw/postings_description_equity/firm_merge/latest_postings_llm_firm_merge.csv)

`make data` reruns the deterministic pieces around that branch, but it does not
replace the manual Batch step itself.

For the full details, see:

- [`postings_equity_workflow.md`](postings_equity_workflow.md)

## Phase 2: `make specs`

`make specs` runs the empirical Stata layer.

### What it does

1. regenerates the contract-derived docs from
   [`writeup/py/paper_support/paper_asset_contract.json`](../writeup/py/paper_support/paper_asset_contract.json)
2. runs the active table-side Stata specs
3. runs the active figure-side Stata specs

### What it reads

- canonical datasets under [`data/clean/`](../data/clean/)

### What it writes

- machine-readable exports under [`results/raw/`](../results/raw/)
- spec logs under [`log/`](../log/) and [`log/batch/`](../log/batch/)

The active Stata surfaces are:

- [`spec/stata/tables/`](../spec/stata/tables/)
- [`spec/stata/figures/`](../spec/stata/figures/)

## Phase 3: `make paper`

`make paper` runs the final paper-facing builders.

### What it does

1. regenerates the contract-derived docs again
2. runs the table builders
3. runs the figure builders

### What it reads

Two valid paper-builder input modes:

- descriptive assets:
  - canonical cleaned data in [`data/clean/`](../data/clean/)
- estimation-driven assets:
  - empirical exports in [`results/raw/`](../results/raw/)

### What it writes

- [`results/cleaned/tex/`](../results/cleaned/tex/)
- [`results/cleaned/figures/`](../results/cleaned/figures/)
- [`results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/`](../results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/)

## Logs And Inspection Points

When something goes wrong, inspect:

- [`log/`](../log/)
  - script-level logs
- [`log/batch/`](../log/batch/)
  - outer Stata batch transcripts
- [`results/raw/`](../results/raw/)
  - machine-readable empirical outputs
- [`results/cleaned/`](../results/cleaned/)
  - final manuscript-facing outputs

## Most Useful Manual Reruns

Rerun one upstream Python script:

```bash
./bin/project-python src/py/build_user_attributes.py
```

Rerun one upstream Stata script:

```bash
./bin/stata -b do src/stata/build_firm_panel.do
```

Rerun one table-side Stata spec:

```bash
./bin/stata -b do spec/stata/tables/01_user_productivity_precovid_total_ols_single.do precovid
```

Rerun one paper-facing builder:

```bash
./bin/project-python writeup/py/figures/user_event_study_precovid_ols.py
```

## Where Overleaf Fits

The repo builds the in-scope manuscript assets first. Overleaf is downstream.

The active paper lane is defined by:

- [`writeup/py/paper_support/paper_asset_contract.json`](../writeup/py/paper_support/paper_asset_contract.json)

The generated manuscript-facing lineage docs are:

- [`main_tex_assets.md`](main_tex_assets.md)
- [`paper_table_lineage.md`](paper_table_lineage.md)
- [`figure_lineage.md`](figure_lineage.md)

Those docs also make the out-of-scope active manuscript assets explicit.
