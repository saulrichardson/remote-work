# `spec/stata/figures/`

This folder contains the active figure-side numbered Stata specs for the
repo-owned paper lane.

Use this file when you want to know:

- which `.do` file owns an active manuscript figure
- which figures are descriptive versus estimation-driven
- where the raw figure exports land before Python renders final PNGs

## What This Folder Owns

This folder owns the empirical-export side of the active figure lane.

That means:

- inputs come from canonical datasets in `data/clean/`
- outputs land in `results/raw/`
- final PNG rendering happens downstream in `writeup/py/`

## Counts

- Active repo-owned figure assets in `main.tex`: `20`
- Stata-backed active figure assets: `18`
- Non-Stata active figure assets: `2`

The two non-Stata figures are the descriptive core firm figures:

- `firm_age_lt100_remote.png`
- `firm_teleworkable_remote.png`

## How To Run

Run the grouped empirical spec lane:

```bash
make specs
```

Run one figure owner directly:

```bash
./bin/stata -b do spec/stata/figures/01_user_event_study_precovid_ols.do precovid
./bin/stata -b do spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do
```

## Active Figure-Side Owners

- `01_user_event_study_precovid_ols.do`
  - raw inputs for `user_event_study_precovid_ols.png`
- `02_firm_event_study_growth_ols.do`
  - raw inputs for `firm_event_study_growth_ols.png`
- `03_startup_cutoff_bars_total_contributions_q100.do`
  - raw inputs for `startup_cutoff_bars_total_contributions_q100.png`
- `04_startup_cutoff_bars_growth_rate_we.do`
  - raw inputs for `startup_cutoff_bars_growth_rate_we.png`
- `05_firm_event_study_join_rate_ols.do`
  - raw inputs for `firm_event_study_join_rate_ols.png`
- `06_firm_event_study_leave_rate_ols.do`
  - raw inputs for `firm_event_study_leave_rate_ols.png`
- `07_firm_event_study_job_postings_ols.do`
  - raw inputs for `firm_event_study_job_postings_ols.png`
- `08_firm_event_study_hires_per_job_posting_ols.do`
  - raw inputs for `firm_event_study_hires_per_job_posting_ols.png`
- `09_user_event_study_fullrem_precovid_ols.do`
  - raw inputs for `user_event_study_fullrem_precovid_ols.png`
- `10_firm_event_study_fullrem_growth_ols.do`
  - raw inputs for `firm_event_study_fullrem_growth_ols.png`
- `11_firm_event_study_fullrem_join_rate_ols.do`
  - raw inputs for `firm_event_study_fullrem_join_rate_ols.png`
- `12_firm_event_study_fullrem_leave_rate_ols.do`
  - raw inputs for `firm_event_study_fullrem_leave_rate_ols.png`
- `13_firm_event_study_fullrem_job_postings_ols.do`
  - raw inputs for `firm_event_study_fullrem_job_postings_ols.png`
- `14_firm_event_study_fullrem_hires_per_job_posting_ols.do`
  - raw inputs for `firm_event_study_fullrem_hires_per_job_posting_ols.png`
- `15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do`
  - raw inputs for `crunchbase_fundraising_event_study_raised_usd_mil_ols.png`
- `16_panelB_fullremote_engineer.do`
  - raw inputs for `panelB_fullremote_engineer.png`
- `17_panelB_fullremote_nonengineer.do`
  - raw inputs for `panelB_fullremote_nonengineer.png`
- `18_user_hire_event_study_remote_rank_mw.do`
  - raw inputs for `user_hire_event_study_remote_rank_mw.png`

## Special Cases

The two descriptive figures without Stata owners are built directly by:

- [`../../../writeup/py/figures/01_firm_age_lt100_remote.py`](../../../writeup/py/figures/01_firm_age_lt100_remote.py)
- [`../../../writeup/py/figures/02_firm_teleworkable_remote.py`](../../../writeup/py/figures/02_firm_teleworkable_remote.py)

## Related Docs

- [`../README.md`](../README.md)
- [`../../../docs/core_specs.md`](../../../docs/core_specs.md)
- [`../../../docs/figure_lineage.md`](../../../docs/figure_lineage.md)
