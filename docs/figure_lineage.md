# Figure Lineage

This document is generated from the active logic-owned paper asset contract.

It answers three questions:

1. which active Stata scripts feed the in-scope figures
2. which active Python builders render the final images
3. where the final cleaned files are written

For the exact active `main.tex` inventory, start with
[`main_tex_assets.md`](main_tex_assets.md).

## Active output locations

- `results/cleaned/tex`
- `results/cleaned/figures`
- `results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid`

## Input modes

- Descriptive figures:
  - the core firm figures have no Stata owner and read canonical cleaned datasets
    directly from `data/clean/`
- Estimation-driven figures:
  - all remaining in-scope figures run through `spec/stata/figures/`, write
    machine-readable outputs to `results/raw/`, and then render final PNGs from there

## Family 1: Core Firm Figures

- `firm_age_lt100_remote.png`
  - Stata: none
  - Python builder: `writeup/py/figures/01_firm_age_lt100_remote.py`
  - Input: `data/clean/firm_panel.dta`
  - Input: `data/clean/user_panel_precovid.dta`
- `firm_teleworkable_remote.png`
  - Stata: none
  - Python builder: `writeup/py/figures/02_firm_teleworkable_remote.py`
  - Input: `data/clean/firm_panel.dta`
  - Input: `data/clean/user_panel_precovid.dta`

## Family 2: Event-Study Figures

- `user_event_study_precovid_ols.png`
  - Stata: `spec/stata/figures/01_user_event_study_precovid_ols.do precovid`
  - Python builder: `writeup/py/figures/user_event_study_precovid_ols.py`
  - Raw output: `results/raw/01_user_event_study_precovid_ols/ols_total_contributions_q100.csv`
- `firm_event_study_growth_ols.png`
  - Stata: `spec/stata/figures/02_firm_event_study_growth_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_growth_ols.py`
  - Raw output: `results/raw/02_firm_event_study_growth_ols/ols_growth_rate_we.csv`
- `firm_event_study_join_rate_ols.png`
  - Stata: `spec/stata/figures/05_firm_event_study_join_rate_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_join_rate_ols.py`
  - Raw output: `results/raw/05_firm_event_study_join_rate_ols/ols_join_rate_we.csv`
- `firm_event_study_leave_rate_ols.png`
  - Stata: `spec/stata/figures/06_firm_event_study_leave_rate_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_leave_rate_ols.py`
  - Raw output: `results/raw/06_firm_event_study_leave_rate_ols/ols_leave_rate_we.csv`
- `firm_event_study_job_postings_ols.png`
  - Stata: `spec/stata/figures/07_firm_event_study_job_postings_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_job_postings_ols.py`
  - Raw output: `results/raw/07_firm_event_study_job_postings_ols/ols_vacancies_thousands.csv`
- `firm_event_study_hires_per_job_posting_ols.png`
  - Stata: `spec/stata/figures/08_firm_event_study_hires_per_job_posting_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_hires_per_job_posting_ols.py`
  - Raw output: `results/raw/08_firm_event_study_hires_per_job_posting_ols/ols_hires_to_vacancies_winsor.csv`
- `user_event_study_fullrem_precovid_ols.png`
  - Stata: `spec/stata/figures/09_user_event_study_fullrem_precovid_ols.do precovid`
  - Python builder: `writeup/py/figures/user_event_study_fullrem_precovid_ols.py`
  - Raw output: `results/raw/09_user_event_study_fullrem_precovid_ols/ols_total_contributions_q100.csv`
- `firm_event_study_fullrem_growth_ols.png`
  - Stata: `spec/stata/figures/10_firm_event_study_fullrem_growth_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_fullrem_growth_ols.py`
  - Raw output: `results/raw/10_firm_event_study_fullrem_growth_ols/ols_growth_rate_we.csv`
- `firm_event_study_fullrem_join_rate_ols.png`
  - Stata: `spec/stata/figures/11_firm_event_study_fullrem_join_rate_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_fullrem_join_rate_ols.py`
  - Raw output: `results/raw/11_firm_event_study_fullrem_join_rate_ols/ols_join_rate_we.csv`
- `firm_event_study_fullrem_leave_rate_ols.png`
  - Stata: `spec/stata/figures/12_firm_event_study_fullrem_leave_rate_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_fullrem_leave_rate_ols.py`
  - Raw output: `results/raw/12_firm_event_study_fullrem_leave_rate_ols/ols_leave_rate_we.csv`
- `firm_event_study_fullrem_job_postings_ols.png`
  - Stata: `spec/stata/figures/13_firm_event_study_fullrem_job_postings_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_fullrem_job_postings_ols.py`
  - Raw output: `results/raw/13_firm_event_study_fullrem_job_postings_ols/ols_vacancies_thousands.csv`
- `firm_event_study_fullrem_hires_per_job_posting_ols.png`
  - Stata: `spec/stata/figures/14_firm_event_study_fullrem_hires_per_job_posting_ols.do`
  - Python builder: `writeup/py/figures/firm_event_study_fullrem_hires_per_job_posting_ols.py`
  - Raw output: `results/raw/14_firm_event_study_fullrem_hires_per_job_posting_ols/ols_hires_to_vacancies_winsor.csv`
- `crunchbase_fundraising_event_study_raised_usd_mil_ols.png`
  - Stata: `spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do`
  - Python builder: `writeup/py/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.py`
  - Raw output: `results/raw/15_crunchbase_fundraising_event_study_raised_usd_mil_ols/ols_cb_raised_usd_mil.csv`

## Family 3: Startup-Cutoff Figures

- `startup_cutoff_bars_total_contributions_q100.png`
  - Stata: `spec/stata/figures/03_startup_cutoff_bars_total_contributions_q100.do precovid`
  - Python builder: `writeup/py/startup_cutoff/03_startup_cutoff_bars_total_contributions_q100.py`
  - Raw output: `results/raw/03_startup_cutoff_bars_total_contributions_q100/user_productivity/consolidated_results.csv`
- `startup_cutoff_bars_growth_rate_we.png`
  - Stata: `spec/stata/figures/04_startup_cutoff_bars_growth_rate_we.do precovid`
  - Python builder: `writeup/py/startup_cutoff/04_startup_cutoff_bars_growth_rate_we.py`
  - Raw output: `results/raw/04_startup_cutoff_bars_growth_rate_we/firm_scaling/consolidated_results.csv`

## Family 4: Engineer / Non-Engineer IRFs

- `panelB_fullremote_engineer.png`
  - Stata: `spec/stata/figures/16_panelB_fullremote_engineer.do`
  - Python builder: `writeup/py/figures/panelB_fullremote_engineer.py`
  - Raw output: `results/raw/16_panelB_fullremote_engineer/remote1/eng_noneng_irf_estimates.dta`
  - Raw output: `results/raw/16_panelB_fullremote_engineer/remote1/eng_noneng_irf_results.csv`
- `panelB_fullremote_nonengineer.png`
  - Stata: `spec/stata/figures/17_panelB_fullremote_nonengineer.do`
  - Python builder: `writeup/py/figures/panelB_fullremote_nonengineer.py`
  - Raw output: `results/raw/17_panelB_fullremote_nonengineer/remote1/eng_noneng_irf_estimates.dta`
  - Raw output: `results/raw/17_panelB_fullremote_nonengineer/remote1/eng_noneng_irf_results.csv`

## Family 5: Remote-Hire Event Study

- `user_hire_event_study_remote_rank_mw.png`
  - Stata: `spec/stata/figures/18_user_hire_event_study_remote_rank_mw.do`
  - Python builder: `writeup/py/user_hire/18_user_hire_event_study_remote_rank_mw.py`
  - Raw output: `results/raw/18_user_hire_event_study_remote_rank_mw/ols_results.csv`

## Excluded active figures

These figure assets are still active in the manuscript, but they are intentionally outside
the repo-owned local build contract. The public local commands do not generate them.

- `../Figures/Demeaned_Indiv_WithinFirmPromotions.jpg`
  - Reason: `external_figure`
  - Source: `../Figures/Demeaned_Indiv_WithinFirmPromotions.jpg`
  - Note: Active external figure omitted from the repo-owned paper lane.
- `../Figures/Demeaned_Indiv_Publications.jpg`
  - Reason: `external_figure`
  - Source: `../Figures/Demeaned_Indiv_Publications.jpg`
  - Note: Active external figure omitted from the repo-owned paper lane.
- `../Figures/Demeaned_TobinsQ.jpg`
  - Reason: `external_figure`
  - Source: `../Figures/Demeaned_TobinsQ.jpg`
  - Note: Active external figure omitted from the repo-owned paper lane.
- `../Figures/Demeaned_OrgCapital.jpg`
  - Reason: `external_figure`
  - Source: `../Figures/Demeaned_OrgCapital.jpg`
  - Note: Active external figure omitted from the repo-owned paper lane.

## Status

- The active logic-owned figure lane reruns from the contract-defined Stata and Python surface.
- Any active external figure still used by the manuscript is explicit in the exclusion section above.
