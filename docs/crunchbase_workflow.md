# Crunchbase Workflow

This runbook documents the active Crunchbase branch from raw files to final
paper assets.

## What This Branch Produces

Canonical upstream datasets:

- [`../data/clean/crunchbase_crosswalk.csv`](../data/clean/crunchbase_crosswalk.csv)
- [`../data/clean/firm_panel_with_cb.csv`](../data/clean/firm_panel_with_cb.csv)
- [`../data/clean/firm_panel_with_cb_funding.csv`](../data/clean/firm_panel_with_cb_funding.csv)

Empirical outputs:

- `results/raw/03_firm_scaling_crunchbase_fundraising_core4/`
- `results/raw/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd/`
- `results/raw/15_crunchbase_fundraising_event_study_raised_usd_mil_ols/`

Final paper assets:

- [`../results/cleaned/tex/firm_scaling_crunchbase_fundraising_core4.tex`](../results/cleaned/tex/firm_scaling_crunchbase_fundraising_core4.tex)
- [`../results/cleaned/tex/firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex`](../results/cleaned/tex/firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex)
- [`../results/cleaned/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.png`](../results/cleaned/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.png)

## Raw Source Boundary

Required raw inputs:

- [`../data/raw/crunchbase/organizations.csv`](../data/raw/crunchbase/organizations.csv)
- [`../data/raw/crunchbase/funding_rounds.csv`](../data/raw/crunchbase/funding_rounds.csv)

## Upstream Data Steps

### 1. Build the firm-to-Crunchbase crosswalk

```bash
./bin/project-python src/py/build_crunchbase_crosswalk.py
```

Output:

- [`../data/clean/crunchbase_crosswalk.csv`](../data/clean/crunchbase_crosswalk.csv)

### 2. Build the firm panel with Crunchbase IDs

```bash
./bin/project-python src/py/build_firm_panel_with_crunchbase.py
```

Inputs:

- [`../data/clean/firm_panel.dta`](../data/clean/firm_panel.dta)
- [`../data/clean/crunchbase_crosswalk.csv`](../data/clean/crunchbase_crosswalk.csv)

Output:

- [`../data/clean/firm_panel_with_cb.csv`](../data/clean/firm_panel_with_cb.csv)

### 3. Merge half-year fundraising outcomes

```bash
./bin/project-python src/py/build_firm_panel_with_crunchbase_funding.py
```

Inputs:

- [`../data/clean/firm_panel_with_cb.csv`](../data/clean/firm_panel_with_cb.csv)
- [`../data/raw/crunchbase/funding_rounds.csv`](../data/raw/crunchbase/funding_rounds.csv)

Output:

- [`../data/clean/firm_panel_with_cb_funding.csv`](../data/clean/firm_panel_with_cb_funding.csv)

## Empirical Step

The active empirical owners are:

- [`../spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do`](../spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do)
- [`../spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do`](../spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do)
- [`../spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do`](../spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do)

Representative commands:

```bash
./bin/stata -b do spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do
./bin/stata -b do spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do
./bin/stata -b do spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do
```

## Final Paper Builders

```bash
./bin/project-python writeup/py/firm_scaling/03_firm_scaling_crunchbase_fundraising_core4.py
./bin/project-python writeup/py/firm_scaling/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.py
./bin/project-python writeup/py/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.py
```

## Grouped Commands

This branch is already covered by the public commands:

```bash
make data
make specs
make paper
```
