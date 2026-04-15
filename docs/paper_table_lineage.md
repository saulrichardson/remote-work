# Paper Table Lineage

This file is generated from the active logic-owned paper asset contract.

Grounding:

- contract: `writeup/py/paper_support/paper_asset_contract.json`
- Overleaf paper path: `/Users/saulrichardson/Dropbox/Apps/Overleaf/WFH Startups/Current/Paper/main.tex`
- active table-side Stata implementations under `spec/stata/tables/`
- active Python builders under `writeup/py/`
- raw outputs under `results/raw/`
- cleaned table fragments under `results/cleaned/tex/`

## Counts

- In-scope active table fragments in `main.tex`: `18`
- In-scope fragments built from active Stata exports: `16`
- Active table-side logical owners in this repo-owned lane: `15`
- In-scope table assets without their own Stata owner: `2`
- Downstream-only in-scope table assets: `1`
- Excluded active table assets: `1`

## Input modes

- Descriptive or hybrid tables without their own Stata owner:
  - `table_of_means.tex` reads canonical cleaned data directly and also uses the upstream
    postings-equity branch
  - `first_stage_summary.tex` is downstream-only and summarizes already-exported spec outputs
- Estimation-driven tables:
  - the remaining in-scope tables run through `spec/stata/tables/` and read `results/raw/`

## In-scope active tables in paper order

5. `table_of_means.tex`
   - Stata: none
   - Python builder: `writeup/py/paper_support/table_of_means.py`
   - Upstream input: `data/clean/firm_panel.dta`
   - Upstream input: `data/clean/user_panel_precovid.dta`
   - Upstream input: `results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`

6. `user_productivity_precovid_total_ols_single.tex`
   - Stata: `spec/stata/tables/01_user_productivity_precovid_total_ols_single.do precovid`
   - Raw output: `results/raw/01_user_productivity_precovid_total_ols_single/baseline_main_effect`
   - Raw output: `results/raw/01_user_productivity_precovid_total_ols_single/interacted_columns`
   - Python builder: `writeup/py/user_productivity/01_user_productivity_precovid_total_ols_single.py`
   - Upstream input: `data/clean/user_panel_precovid.dta`

7. `user_productivity_precovid_total_iv_single.tex`
   - Stata: `spec/stata/tables/02_user_productivity_precovid_total_iv_single.do precovid`
   - Raw output: `results/raw/02_user_productivity_precovid_total_iv_single/baseline_main_effect`
   - Raw output: `results/raw/02_user_productivity_precovid_total_iv_single/interacted_columns`
   - Raw output: `results/raw/02_user_productivity_precovid_total_iv_single/first_stage`
   - Python builder: `writeup/py/user_productivity/02_user_productivity_precovid_total_iv_single.py`
   - Upstream input: `data/clean/user_panel_precovid.dta`

8. `firm_scaling_crunchbase_fundraising_core4.tex`
   - Stata: `spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do`
   - Raw output: `results/raw/03_firm_scaling_crunchbase_fundraising_core4`
   - Python builder: `writeup/py/firm_scaling/03_firm_scaling_crunchbase_fundraising_core4.py`
   - Upstream input: `data/clean/firm_panel_with_cb_funding.csv`

9. `firm_scaling_precovid_cols1_4.tex`
   - Stata: `spec/stata/tables/04_firm_scaling_precovid.do`
   - Raw output: `results/raw/04_firm_scaling_precovid/growth_baseline_main_effect`
   - Raw output: `results/raw/04_firm_scaling_precovid/growth_interacted_columns`
   - Raw output: `results/raw/04_firm_scaling_precovid/first_stage`
   - Python builder: `writeup/py/firm_scaling/04_firm_scaling_precovid.py`
   - Upstream input: `data/clean/firm_panel.dta`
   - Upstream input: `data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv`

10. `firm_scaling_precovid_cols5_6.tex`
   - Stata: `spec/stata/tables/04_firm_scaling_precovid.do`
   - Raw output: `results/raw/04_firm_scaling_precovid/vacancy_interacted_columns`
   - Python builder: `writeup/py/firm_scaling/04_firm_scaling_precovid.py`
   - Upstream input: `data/clean/firm_panel.dta`
   - Upstream input: `data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv`

11. `user_mechanisms_keep_remote_precovid.tex`
   - Stata: `spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do precovid`
   - Raw output: `results/raw/05_user_mechanisms_keep_remote_precovid`
   - Python builder: `writeup/py/user_productivity/05_user_mechanisms_keep_remote_precovid.py --variant precovid`
   - Upstream input: `data/clean/user_panel_precovid.dta`
   - Upstream input: `data/clean/firm_panel.dta`
   - Upstream input: `results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`

12. `user_wage_fe_variants_precovid_log_salary.tex`
   - Stata: `spec/stata/tables/06_user_wage_fe_variants_precovid_log_salary.do precovid`
   - Raw output: `results/raw/06_user_wage_fe_variants_precovid_log_salary`
   - Python builder: `writeup/py/user_productivity/06_user_wage_fe_variants_precovid_log_salary.py --variant precovid`
   - Upstream input: `data/clean/user_panel_precovid.dta`

13. `user_productivity_fr_focus_precovid.tex`
   - Stata: `spec/stata/tables/07_user_productivity_fr_focus_precovid.do precovid`
   - Raw output: `results/raw/07_user_productivity_fr_focus_precovid/fr_vs_all`
   - Raw output: `results/raw/07_user_productivity_fr_focus_precovid/fr_vs_hyb`
   - Python builder: `writeup/py/user_productivity/07_user_productivity_fr_focus_precovid.py --variant precovid`
   - Upstream input: `data/clean/user_panel_precovid.dta`

14. `user_productivity_top_metros_firmbyuser.tex`
   - Stata: `spec/stata/tables/08_user_productivity_top_metros_firmbyuser.do precovid`
   - Raw output: `results/raw/08_user_productivity_top_metros_firmbyuser/precovid_keeptop5`
   - Raw output: `results/raw/08_user_productivity_top_metros_firmbyuser/precovid_keeptop10`
   - Raw output: `results/raw/08_user_productivity_top_metros_firmbyuser/precovid_droptop5`
   - Raw output: `results/raw/08_user_productivity_top_metros_firmbyuser/precovid_droptop10`
   - Python builder: `writeup/py/user_productivity/08_user_productivity_top_metros_firmbyuser.py`
   - Upstream input: `data/clean/user_panel_precovid.dta`
   - Upstream input: `data/clean/csa_msa_top14_mapping.csv`

15. `user_productivity_traits_dual_precovid_ols.tex`
   - Stata: `spec/stata/tables/09_user_productivity_traits_dual_precovid_ols.do precovid`
   - Raw output: `results/raw/09_user_productivity_traits_dual_precovid_ols`
   - Python builder: `writeup/py/user_productivity/09_user_productivity_traits_dual_precovid_ols.py`
   - Upstream input: `data/clean/user_panel_precovid.dta`
   - Upstream input: `data/clean/user_attributes.dta`

16. `user_productivity_precovid_nonsoftware.tex`
   - Stata: `spec/stata/tables/10_user_productivity_precovid_nonsoftware.do precovid`
   - Raw output: `results/raw/10_user_productivity_precovid_nonsoftware/naics_software`
   - Raw output: `results/raw/10_user_productivity_precovid_nonsoftware/soc_strict_new`
   - Raw output: `results/raw/10_user_productivity_precovid_nonsoftware/exclude_ca_ny`
   - Python builder: `writeup/py/user_productivity/10_user_productivity_precovid_nonsoftware.py --variant precovid`
   - Upstream input: `data/clean/user_panel_precovid.dta`

33. `first_stage_summary.tex`
   - Stata: none
   - Python builder: `writeup/py/user_productivity/11_first_stage_summary.py`
   - Upstream input: `results/raw/02_user_productivity_precovid_total_iv_single/first_stage/consolidated_results.csv`
   - Upstream input: `results/raw/04_firm_scaling_precovid/first_stage/consolidated_results.csv`

34. `user_productivity_precovid_restricted.tex`
   - Stata: `spec/stata/tables/11_user_productivity_precovid_restricted.do precovid`
   - Raw output: `results/raw/11_user_productivity_precovid_restricted/baseline_main_effect`
   - Raw output: `results/raw/11_user_productivity_precovid_restricted/interacted_columns`
   - Python builder: `writeup/py/user_productivity/11_user_productivity_precovid_restricted.py`
   - Upstream input: `data/clean/user_panel_precovid.dta`

35. `user_productivity_precovid_stayer_table3.tex`
   - Stata: `spec/stata/tables/12_user_productivity_precovid_stayer_table3.do precovid`
   - Raw output: `results/raw/12_user_productivity_precovid_stayer_table3/baseline_main_effect`
   - Raw output: `results/raw/12_user_productivity_precovid_stayer_table3/interacted_columns`
   - Python builder: `writeup/py/user_productivity/12_user_productivity_precovid_stayer_table3.py --variant precovid`
   - Upstream input: `data/clean/user_panel_precovid.dta`

36. `user_productivity_precovid_industry_hqstate_shocks.tex`
   - Stata: `spec/stata/tables/13_user_productivity_precovid_industry_hqstate_shocks.do precovid`
   - Raw output: `results/raw/13_user_productivity_precovid_industry_hqstate_shocks`
   - Python builder: `writeup/py/user_productivity/13_user_productivity_precovid_industry_hqstate_shocks.py --variant precovid`
   - Upstream input: `data/clean/user_panel_precovid.dta`

37. `firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex`
   - Stata: `spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do`
   - Raw output: `results/raw/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd`
   - Python builder: `writeup/py/firm_scaling/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.py`
   - Upstream input: `data/clean/firm_panel_with_cb_funding.csv`

43. `firm_scaling_location_ratios.tex`
   - Stata: `spec/stata/tables/15_firm_scaling_location_ratios.do`
   - Raw output: `results/raw/15_firm_scaling_location_ratios`
   - Python builder: `writeup/py/firm_scaling/15_firm_scaling_location_ratios.py`
   - Upstream input: `data/clean/firm_panel.dta`
   - Upstream input: `data/clean/firm_geography_counts_imputed.csv`

## Excluded active table assets

These table assets are still active in the manuscript, but they are intentionally outside
the repo-owned local build contract. The public local commands do not generate them.

- `../Results/Tables/Final.tex`
  - Reason: `no_generator_in_repo`
  - Source: `writeup/static_tables/Final.tex`
  - Note: Active table omitted from the logic-owned paper lane because the empirical generator has not been recovered in this repo.

## Current status

- The in-scope table lane is driven from one asset contract and no longer from hand-maintained build lists.
- `Final.tex` remains explicit but excluded because its empirical generator is not recovered in the repo.
