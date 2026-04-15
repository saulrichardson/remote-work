# `main.tex` Logic-Owned Asset Map

This file is generated from
`writeup/py/paper_support/paper_asset_contract.json` and documents the active logic-owned paper lane only.

Active `main.tex` path: `/Users/saulrichardson/Dropbox/Apps/Overleaf/WFH Startups/Current/Paper/main.tex`

## Current active counts

- In-scope active table fragments read from `../Results/Tables/`: `18`
- Excluded active table fragments read from `../Results/Tables/`: `1`
- In-scope active figure assets read from `../Results/Figures/`: `20`
- Excluded active figure assets read from `../Figures/`: `4`

## Path types inside the active lane

- Figures without a Stata owner: `2`
- Figures built from Stata exports in `results/raw/`: `18`
- Tables without their own Stata owner: `2`
- Tables built from Stata exports in `results/raw/`: `16`

Interpretation:

- descriptive assets can read canonical datasets in `data/clean/` directly
- estimation-driven assets read `results/raw/` exported by `spec/stata/`
- this is intentional; `results/raw/` is the spec-output layer, not the raw-data layer

## In-scope active figures in paper order

1. `firm_age_lt100_remote.png`
   - Stata export: none
   - Python builder: `writeup/py/figures/01_firm_age_lt100_remote.py`
   - Input: `data/clean/firm_panel.dta`
   - Input: `data/clean/user_panel_precovid.dta`

2. `firm_teleworkable_remote.png`
   - Stata export: none
   - Python builder: `writeup/py/figures/02_firm_teleworkable_remote.py`
   - Input: `data/clean/firm_panel.dta`
   - Input: `data/clean/user_panel_precovid.dta`

3. `user_event_study_precovid_ols.png`
   - Stata export: `spec/stata/figures/01_user_event_study_precovid_ols.do precovid`
   - Python builder: `writeup/py/figures/user_event_study_precovid_ols.py`
   - Raw output: `results/raw/01_user_event_study_precovid_ols/ols_total_contributions_q100.csv`

4. `firm_event_study_growth_ols.png`
   - Stata export: `spec/stata/figures/02_firm_event_study_growth_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_growth_ols.py`
   - Raw output: `results/raw/02_firm_event_study_growth_ols/ols_growth_rate_we.csv`

17. `startup_cutoff_bars_total_contributions_q100.png`
   - Stata export: `spec/stata/figures/03_startup_cutoff_bars_total_contributions_q100.do precovid`
   - Python builder: `writeup/py/startup_cutoff/03_startup_cutoff_bars_total_contributions_q100.py`
   - Raw output: `results/raw/03_startup_cutoff_bars_total_contributions_q100/user_productivity/consolidated_results.csv`

18. `startup_cutoff_bars_growth_rate_we.png`
   - Stata export: `spec/stata/figures/04_startup_cutoff_bars_growth_rate_we.do precovid`
   - Python builder: `writeup/py/startup_cutoff/04_startup_cutoff_bars_growth_rate_we.py`
   - Raw output: `results/raw/04_startup_cutoff_bars_growth_rate_we/firm_scaling/consolidated_results.csv`

19. `firm_event_study_join_rate_ols.png`
   - Stata export: `spec/stata/figures/05_firm_event_study_join_rate_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_join_rate_ols.py`
   - Raw output: `results/raw/05_firm_event_study_join_rate_ols/ols_join_rate_we.csv`

20. `firm_event_study_leave_rate_ols.png`
   - Stata export: `spec/stata/figures/06_firm_event_study_leave_rate_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_leave_rate_ols.py`
   - Raw output: `results/raw/06_firm_event_study_leave_rate_ols/ols_leave_rate_we.csv`

21. `firm_event_study_job_postings_ols.png`
   - Stata export: `spec/stata/figures/07_firm_event_study_job_postings_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_job_postings_ols.py`
   - Raw output: `results/raw/07_firm_event_study_job_postings_ols/ols_vacancies_thousands.csv`

22. `firm_event_study_hires_per_job_posting_ols.png`
   - Stata export: `spec/stata/figures/08_firm_event_study_hires_per_job_posting_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_hires_per_job_posting_ols.py`
   - Raw output: `results/raw/08_firm_event_study_hires_per_job_posting_ols/ols_hires_to_vacancies_winsor.csv`

23. `user_event_study_fullrem_precovid_ols.png`
   - Stata export: `spec/stata/figures/09_user_event_study_fullrem_precovid_ols.do precovid`
   - Python builder: `writeup/py/figures/user_event_study_fullrem_precovid_ols.py`
   - Raw output: `results/raw/09_user_event_study_fullrem_precovid_ols/ols_total_contributions_q100.csv`

24. `firm_event_study_fullrem_growth_ols.png`
   - Stata export: `spec/stata/figures/10_firm_event_study_fullrem_growth_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_fullrem_growth_ols.py`
   - Raw output: `results/raw/10_firm_event_study_fullrem_growth_ols/ols_growth_rate_we.csv`

25. `firm_event_study_fullrem_join_rate_ols.png`
   - Stata export: `spec/stata/figures/11_firm_event_study_fullrem_join_rate_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_fullrem_join_rate_ols.py`
   - Raw output: `results/raw/11_firm_event_study_fullrem_join_rate_ols/ols_join_rate_we.csv`

26. `firm_event_study_fullrem_leave_rate_ols.png`
   - Stata export: `spec/stata/figures/12_firm_event_study_fullrem_leave_rate_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_fullrem_leave_rate_ols.py`
   - Raw output: `results/raw/12_firm_event_study_fullrem_leave_rate_ols/ols_leave_rate_we.csv`

27. `firm_event_study_fullrem_job_postings_ols.png`
   - Stata export: `spec/stata/figures/13_firm_event_study_fullrem_job_postings_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_fullrem_job_postings_ols.py`
   - Raw output: `results/raw/13_firm_event_study_fullrem_job_postings_ols/ols_vacancies_thousands.csv`

28. `firm_event_study_fullrem_hires_per_job_posting_ols.png`
   - Stata export: `spec/stata/figures/14_firm_event_study_fullrem_hires_per_job_posting_ols.do`
   - Python builder: `writeup/py/figures/firm_event_study_fullrem_hires_per_job_posting_ols.py`
   - Raw output: `results/raw/14_firm_event_study_fullrem_hires_per_job_posting_ols/ols_hires_to_vacancies_winsor.csv`

29. `crunchbase_fundraising_event_study_raised_usd_mil_ols.png`
   - Stata export: `spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do`
   - Python builder: `writeup/py/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.py`
   - Raw output: `results/raw/15_crunchbase_fundraising_event_study_raised_usd_mil_ols/ols_cb_raised_usd_mil.csv`

30. `panelB_fullremote_engineer.png`
   - Stata export: `spec/stata/figures/16_panelB_fullremote_engineer.do`
   - Python builder: `writeup/py/figures/panelB_fullremote_engineer.py`
   - Raw output: `results/raw/16_panelB_fullremote_engineer/remote1/eng_noneng_irf_estimates.dta`
   - Raw output: `results/raw/16_panelB_fullremote_engineer/remote1/eng_noneng_irf_results.csv`

31. `panelB_fullremote_nonengineer.png`
   - Stata export: `spec/stata/figures/17_panelB_fullremote_nonengineer.do`
   - Python builder: `writeup/py/figures/panelB_fullremote_nonengineer.py`
   - Raw output: `results/raw/17_panelB_fullremote_nonengineer/remote1/eng_noneng_irf_estimates.dta`
   - Raw output: `results/raw/17_panelB_fullremote_nonengineer/remote1/eng_noneng_irf_results.csv`

32. `user_hire_event_study_remote_rank_mw.png`
   - Stata export: `spec/stata/figures/18_user_hire_event_study_remote_rank_mw.do`
   - Python builder: `writeup/py/user_hire/18_user_hire_event_study_remote_rank_mw.py`
   - Raw output: `results/raw/18_user_hire_event_study_remote_rank_mw/ols_results.csv`

## In-scope active tables

The `18` in-scope active `../Results/Tables/...` fragments are documented in
[`paper_table_lineage.md`](paper_table_lineage.md).

## Excluded active assets

These assets are still active in the current Overleaf manuscript, but they are intentionally
outside the repo-owned local build contract. `make data`, `make specs`, and `make paper`
do not generate them.

- `../Results/Tables/Final.tex`
  - Reason: `no_generator_in_repo`
  - Source: `writeup/static_tables/Final.tex`
  - Note: Active table omitted from the logic-owned paper lane because the empirical generator has not been recovered in this repo.
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

## Current status

- The active logic-owned paper lane is now derived from one contract file.
- Any active `main.tex` asset not represented in the build is explicit in the exclusion list above.
- `make paper` rebuilds the in-scope cleaned outputs defined by this contract.
