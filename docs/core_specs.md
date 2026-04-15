# Core Specifications

This document explains the main empirical approaches behind the active
repo-owned paper lane.

It is not a substitute for reading the Stata code. Its role is to make the
high-level designs legible:

- unit of observation
- key regressors
- identification strategy
- output family
- owning spec files

For the exact asset-by-asset lineage, use:

- [`paper_table_lineage.md`](paper_table_lineage.md)
- [`figure_lineage.md`](figure_lineage.md)

## Shared Setup

### Time unit

Most of the active paper lane works on half-year panels indexed by `yh`.

In the main baseline designs:

- `covid = yh >= 120`
- `120` corresponds to `2020H1`

### Core remote / startup interaction design

The central treatment pattern used in the baseline panel regressions is:

- `remote`
  - firm-level remote exposure or remoteness score
- `startup`
  - firm age threshold indicator
- `covid`
  - post-period indicator

Shared interaction variables:

- `var3 = remote * covid`
- `var4 = covid * startup`
- `var5 = remote * covid * startup`

For IV specifications, teleworkability interactions instrument the remote terms:

- `var6 = covid * teleworkable`
- `var7 = startup * covid * teleworkable`

Those constructs are built upstream in the canonical panels:

- [`src/stata/build_firm_panel.do`](../src/stata/build_firm_panel.do)
- [`src/stata/build_all_user_panels.do`](../src/stata/build_all_user_panels.do)

## 1. User Productivity Family

### What this family studies

How remote exposure changes worker productivity, especially for startup firms,
using worker-by-half-year panels.

### Unit of observation

- `user_id × yh`

### Main input

- [`data/clean/user_panel_precovid.dta`](../data/clean/user_panel_precovid.dta)

### Main outcomes

- `total_contributions_q100`
- related contribution variants in robustness tables

### Baseline OLS design

Core active owner:

- [`spec/stata/tables/01_user_productivity_precovid_total_ols_single.do`](../spec/stata/tables/01_user_productivity_precovid_total_ols_single.do)

Representative baseline column:

```stata
reghdfe outcome var3 var4, absorb(user_id firm_id yh) vce(cluster user_id)
```

Later columns add the triple interaction `var5` and alternative fixed-effect
structures, including match fixed effects:

- `absorb(firm_id user_id yh)`
- `absorb(firm_id#user_id yh)`

### Baseline IV design

Core active owner:

- [`spec/stata/tables/02_user_productivity_precovid_total_iv_single.do`](../spec/stata/tables/02_user_productivity_precovid_total_iv_single.do)

Representative IV specification:

```stata
ivreghdfe outcome (var3 var5 = var6 var7) var4, absorb(firm_id#user_id yh) vce(cluster user_id)
```

### Active downstream outputs

Main table family:

- `user_productivity_precovid_total_ols_single.tex`
- `user_productivity_precovid_total_iv_single.tex`
- `user_productivity_precovid_restricted.tex`
- `user_productivity_precovid_stayer_table3.tex`
- `user_productivity_precovid_industry_hqstate_shocks.tex`
- `user_productivity_fr_focus_precovid.tex`
- `user_productivity_top_metros_firmbyuser.tex`
- `user_productivity_traits_dual_precovid_ols.tex`
- `user_productivity_precovid_nonsoftware.tex`
- `user_wage_fe_variants_precovid_log_salary.tex`

### Related specs and builders

Stata:

- [`spec/stata/tables/01_user_productivity_precovid_total_ols_single.do`](../spec/stata/tables/01_user_productivity_precovid_total_ols_single.do)
- [`spec/stata/tables/02_user_productivity_precovid_total_iv_single.do`](../spec/stata/tables/02_user_productivity_precovid_total_iv_single.do)
- [`spec/stata/tables/06_user_wage_fe_variants_precovid_log_salary.do`](../spec/stata/tables/06_user_wage_fe_variants_precovid_log_salary.do)
- [`spec/stata/tables/07_user_productivity_fr_focus_precovid.do`](../spec/stata/tables/07_user_productivity_fr_focus_precovid.do)
- [`spec/stata/tables/08_user_productivity_top_metros_firmbyuser.do`](../spec/stata/tables/08_user_productivity_top_metros_firmbyuser.do)
- [`spec/stata/tables/09_user_productivity_traits_dual_precovid_ols.do`](../spec/stata/tables/09_user_productivity_traits_dual_precovid_ols.do)
- [`spec/stata/tables/10_user_productivity_precovid_nonsoftware.do`](../spec/stata/tables/10_user_productivity_precovid_nonsoftware.do)
- [`spec/stata/tables/11_user_productivity_precovid_restricted.do`](../spec/stata/tables/11_user_productivity_precovid_restricted.do)
- [`spec/stata/tables/12_user_productivity_precovid_stayer_table3.do`](../spec/stata/tables/12_user_productivity_precovid_stayer_table3.do)
- [`spec/stata/tables/13_user_productivity_precovid_industry_hqstate_shocks.do`](../spec/stata/tables/13_user_productivity_precovid_industry_hqstate_shocks.do)

Python:

- [`writeup/py/user_productivity/`](../writeup/py/user_productivity/)

## 2. Firm Scaling Family

### What this family studies

How remote exposure and startup status affect firm growth, worker flows, and
vacancy outcomes at the firm-by-half-year level.

### Unit of observation

- `firm_id × yh`

### Main inputs

- [`data/clean/firm_panel.dta`](../data/clean/firm_panel.dta)
- [`data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv`](../data/clean/vacancy/firm_halfyear_panel_MERGED_POST.csv)

### Main outcomes

Core firm outcomes:

- `growth_rate_we`
- `join_rate_we`
- `leave_rate_we`

Vacancy extension outcomes:

- `vacancies`
- `hires_to_vacancies_winsor95_min3`

### Baseline design

Core active owner:

- [`spec/stata/tables/04_firm_scaling_precovid.do`](../spec/stata/tables/04_firm_scaling_precovid.do)

Representative OLS form:

```stata
reghdfe outcome var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
```

Representative IV form:

```stata
ivreghdfe outcome (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
```

### Active downstream outputs

- `firm_scaling_precovid_cols1_4.tex`
- `firm_scaling_precovid_cols5_6.tex`
- `firm_scaling_location_ratios.tex`

### Related specs and builders

Stata:

- [`spec/stata/tables/04_firm_scaling_precovid.do`](../spec/stata/tables/04_firm_scaling_precovid.do)
- [`spec/stata/tables/15_firm_scaling_location_ratios.do`](../spec/stata/tables/15_firm_scaling_location_ratios.do)

Python:

- [`writeup/py/firm_scaling/04_firm_scaling_precovid.py`](../writeup/py/firm_scaling/04_firm_scaling_precovid.py)
- [`writeup/py/firm_scaling/15_firm_scaling_location_ratios.py`](../writeup/py/firm_scaling/15_firm_scaling_location_ratios.py)

## 3. Event-Study Figures

### What this family studies

Dynamic event-time patterns around the post-period for user and firm outcomes.

### General design

The event-study scripts:

1. start from canonical cleaned panels
2. create event-time dummies in Stata
3. export machine-readable coefficient paths into `results/raw/`
4. render final PNGs in Python

### Main families

User event studies:

- productivity event-study
- full-remote productivity event-study

Firm event studies:

- growth
- join rate
- leave rate
- vacancy counts
- hires per posting
- full-remote variants of the same outcomes

### Representative owner

- [`spec/stata/figures/01_user_event_study_precovid_ols.do`](../spec/stata/figures/01_user_event_study_precovid_ols.do)

That script:

- reads [`data/clean/user_panel_precovid.dta`](../data/clean/user_panel_precovid.dta)
- estimates the event-time pattern in Stata
- writes
  [`results/raw/01_user_event_study_precovid_ols/ols_total_contributions_q100.csv`](../results/raw/01_user_event_study_precovid_ols/ols_total_contributions_q100.csv)

The final figure is then rendered by:

- [`writeup/py/figures/user_event_study_precovid_ols.py`](../writeup/py/figures/user_event_study_precovid_ols.py)

## 4. Crunchbase Fundraising Family

### What this family studies

Whether remote exposure is associated with fundraising outcomes among matched
private firms using the Crunchbase-augmented firm panel.

### Main input

- [`data/clean/firm_panel_with_cb_funding.csv`](../data/clean/firm_panel_with_cb_funding.csv)

### Main outcome

- `cb_raised_usd_mil`

### Active outputs

- `firm_scaling_crunchbase_fundraising_core4.tex`
- `firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex`
- `crunchbase_fundraising_event_study_raised_usd_mil_ols.png`

### Owners

Stata:

- [`spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do`](../spec/stata/tables/03_firm_scaling_crunchbase_fundraising_core4.do)
- [`spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do`](../spec/stata/tables/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do)
- [`spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do`](../spec/stata/figures/15_crunchbase_fundraising_event_study_raised_usd_mil_ols.do)

Python:

- [`writeup/py/firm_scaling/03_firm_scaling_crunchbase_fundraising_core4.py`](../writeup/py/firm_scaling/03_firm_scaling_crunchbase_fundraising_core4.py)
- [`writeup/py/firm_scaling/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.py`](../writeup/py/firm_scaling/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.py)
- [`writeup/py/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.py`](../writeup/py/figures/crunchbase_fundraising_event_study_raised_usd_mil_ols.py)

## 5. Postings-Equity Mechanism Branch

### What this branch studies

Whether firms advertise equity compensation in job postings, and how that firm
half-year equity measure relates to the paper’s mechanisms table and summary
statistics.

### Branch structure

This branch is partly deterministic and partly manual:

1. deterministic candidate extraction from posting shards
2. manual OpenAI Batch extraction
3. deterministic merge and firm-half-year aggregation

### Main paper consumers

- [`writeup/py/paper_support/table_of_means.py`](../writeup/py/paper_support/table_of_means.py)
- [`spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do`](../spec/stata/tables/05_user_mechanisms_keep_remote_precovid.do)

### Main upstream output

- [`results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`](../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv)

### Full workflow

- [`postings_equity_workflow.md`](postings_equity_workflow.md)

## 6. Remote-Hire Event Study

### What this design studies

How destination-firm startup status shapes the event-time pattern of worker
outcomes around a hire event.

### Main input

- [`data/clean/user_hire_event_panel_precovid.dta`](../data/clean/user_hire_event_panel_precovid.dta)

### Main output

- `user_hire_event_study_remote_rank_mw.png`

### Owners

Stata:

- [`spec/stata/figures/18_user_hire_event_study_remote_rank_mw.do`](../spec/stata/figures/18_user_hire_event_study_remote_rank_mw.do)

Python:

- [`writeup/py/user_hire/18_user_hire_event_study_remote_rank_mw.py`](../writeup/py/user_hire/18_user_hire_event_study_remote_rank_mw.py)

## 7. Descriptive Direct Builders

Not every final paper asset has a Stata owner.

Some assets are genuinely descriptive and read canonical cleaned datasets
directly:

- [`writeup/py/figures/01_firm_age_lt100_remote.py`](../writeup/py/figures/01_firm_age_lt100_remote.py)
- [`writeup/py/figures/02_firm_teleworkable_remote.py`](../writeup/py/figures/02_firm_teleworkable_remote.py)
- [`writeup/py/paper_support/table_of_means.py`](../writeup/py/paper_support/table_of_means.py)

This is intentional. Those builders are not bypassing the empirical layer by
mistake; they are the empirical layer for descriptive assets.
