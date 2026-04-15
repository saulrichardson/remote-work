# Stata Single-Scope Refactor Status

This file is now a completion note for the March 31, 2026 refactor rather than a forward-looking
prep memo.

The active top-level `spec/stata/` surface has been reduced to paper-order numbered files plus
`_bootstrap.do`, and the active numbered scripts are now self-contained empirical entrypoints.

## Current active counts from `main.tex`

- Active table fragments read from `../Results/Tables/...`: `19`
- Active repo-owned figures read from `../Results/Figures/...`: `20`
- Active external figures read from `../Figures/...`: `4`

## What is complete

### Active top-level Stata surface

`spec/stata/` now contains:

- active paper-order numbered Stata files
- `_bootstrap.do`
- `README.md`
- `support/README.md` only

Non-paper Stata work and superseded broad implementations now live under:

- `spec/archive/stata/`

### Active numbered table-side Stata files

- `01_user_productivity_precovid_total_ols_single.do`
- `02_user_productivity_precovid_total_iv_single.do`
- `03_firm_scaling_crunchbase_fundraising_core4.do`
- `04_firm_scaling_precovid.do`
- `05_user_mechanisms_keep_remote_precovid.do`
- `06_user_wage_fe_variants_precovid_log_salary.do`
- `07_user_productivity_fr_focus_precovid.do`
- `08_user_productivity_top_metros_firmbyuser.do`
- `09_user_productivity_traits_dual_precovid_ols.do`
- `10_user_productivity_precovid_nonsoftware.do`
- `11_first_stage_summary.do`
- `12_user_productivity_precovid_restricted.do`
- `13_user_productivity_precovid_stayer_table3.do`
- `14_user_productivity_precovid_industry_hqstate_shocks.do`
- `15_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do`
- `16_firm_scaling_location_ratios.do`

### Active numbered figure-side Stata files

- `01_user_event_study_precovid_ols.do`
- `02_firm_event_study_growth_ols.do`
- `03_startup_cutoff_bars_total_contributions_q100.do`
- `04_startup_cutoff_bars_growth_rate_we.do`
- `05_firm_event_study_join_rate_ols.do`
- `06_firm_event_study_leave_rate_ols.do`
- `07_firm_event_study_job_postings_ols.do`
- `08_firm_event_study_hires_per_job_posting_ols.do`
- `09_user_event_study_fullrem_precovid_ols.do`
- `10_firm_event_study_fullrem_growth_ols.do`
- `11_firm_event_study_fullrem_join_rate_ols.do`
- `12_firm_event_study_fullrem_leave_rate_ols.do`
- `13_firm_event_study_fullrem_job_postings_ols.do`
- `14_firm_event_study_fullrem_hires_per_job_posting_ols.do`
- `15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do`
- `16_panelB_fullremote_engineer.do`
- `17_panelB_fullremote_nonengineer.do`
- `18_user_hire_event_study_remote_rank_mw.do`

## Support-layer outcome

There are no active empirical helper `.do` files left under `spec/stata/support/`.

The former support scripts were preserved under:

- `spec/archive/stata/paper_refactor_2026_03_31/former_support/`

The only allowed shared `.do` dependency for active numbered scripts is `_bootstrap.do`.

## Remaining work after the Stata refactor

The main remaining work is figure-style reconciliation against the current Overleaf PNGs and any
future cleanup of upstream non-empirical inputs such as paper-support enrichments.

## Verification requirement

Every active numbered Stata script must keep meeting the same standard:

- rerun successfully from `spec/stata/`
- write raw outputs under `results/raw/...`
- avoid calling empirical helper `.do` files
- produce the same paper asset after the paired Python builder runs
- keep the final active Overleaf asset unchanged
