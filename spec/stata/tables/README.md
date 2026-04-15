# `spec/stata/tables/`

This folder contains the active table-side numbered Stata specs for the
repo-owned paper lane.

Use this file when you want to know:

- which `.do` file owns an active table
- which tables are estimation-driven versus descriptive or downstream-only
- where the raw exports for each table family land

## What This Folder Owns

This folder owns the empirical-export side of the active table lane only.

That means:

- inputs come from canonical datasets in `data/clean/`
- outputs land in `results/raw/`
- final LaTeX formatting happens downstream in `writeup/py/`

## Counts

- In-scope active table fragments in `main.tex`: `18`
- Excluded active table fragments in `main.tex`: `1`
- In-scope fragments built from active Stata exports: `16`
- Active table-side logical owners in this folder: `15`
- In-scope table assets without their own Stata owner: `2`
- Downstream-only active table assets: `1`

Interpretation:

- `table_of_means.tex` is descriptive and has no Stata owner
- `first_stage_summary.tex` is downstream-only and summarizes already-exported
  first-stage outputs
- every other in-scope active table runs through this folder

## How To Run

Run the whole active empirical table lane:

```bash
make specs
```

Run one table owner directly:

```bash
./bin/stata -b do spec/stata/tables/01_user_productivity_precovid_total_ols_single.do precovid
./bin/stata -b do spec/stata/tables/04_firm_scaling_precovid.do
```

## Active Table-Side Owners

- `01_user_productivity_precovid_total_ols_single.do`
  - raw outputs for `user_productivity_precovid_total_ols_single.tex`
- `02_user_productivity_precovid_total_iv_single.do`
  - raw outputs for `user_productivity_precovid_total_iv_single.tex`
- `03_firm_scaling_crunchbase_fundraising_core4.do`
  - raw outputs for `firm_scaling_crunchbase_fundraising_core4.tex`
- `04_firm_scaling_precovid.do`
  - raw outputs for both `firm_scaling_precovid_cols1_4.tex` and
    `firm_scaling_precovid_cols5_6.tex`
- `05_user_mechanisms_keep_remote_precovid.do`
  - raw outputs for `user_mechanisms_keep_remote_precovid.tex`
- `06_user_wage_fe_variants_precovid_log_salary.do`
  - raw outputs for `user_wage_fe_variants_precovid_log_salary.tex`
- `07_user_productivity_fr_focus_precovid.do`
  - raw outputs for `user_productivity_fr_focus_precovid.tex`
- `08_user_productivity_top_metros_firmbyuser.do`
  - raw outputs for `user_productivity_top_metros_firmbyuser.tex`
- `09_user_productivity_traits_dual_precovid_ols.do`
  - raw outputs for `user_productivity_traits_dual_precovid_ols.tex`
- `10_user_productivity_precovid_nonsoftware.do`
  - raw outputs for `user_productivity_precovid_nonsoftware.tex`
- `11_user_productivity_precovid_restricted.do`
  - raw outputs for `user_productivity_precovid_restricted.tex`
- `12_user_productivity_precovid_stayer_table3.do`
  - raw outputs for `user_productivity_precovid_stayer_table3.tex`
- `13_user_productivity_precovid_industry_hqstate_shocks.do`
  - raw outputs for `user_productivity_precovid_industry_hqstate_shocks.tex`
- `14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.do`
  - raw outputs for
    `firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.tex`
- `15_firm_scaling_location_ratios.do`
  - raw outputs for `firm_scaling_location_ratios.tex`

## Special Cases

### `table_of_means.tex`

- no Stata owner
- built by [`../../../writeup/py/paper_support/table_of_means.py`](../../../writeup/py/paper_support/table_of_means.py)
- reads canonical cleaned datasets directly plus the upstream equity branch

### `first_stage_summary.tex`

- no direct Stata owner
- built by [`../../../writeup/py/user_productivity/11_first_stage_summary.py`](../../../writeup/py/user_productivity/11_first_stage_summary.py)
- reads first-stage outputs already exported by:
  - `02_user_productivity_precovid_total_iv_single.do`
  - `04_firm_scaling_precovid.do`

### `Final.tex`

- still active in the manuscript
- explicitly excluded from the repo-owned build contract because its generator
  has not been recovered in this repo

## Related Docs

- [`../README.md`](../README.md)
- [`../../../docs/core_specs.md`](../../../docs/core_specs.md)
- [`../../../docs/paper_table_lineage.md`](../../../docs/paper_table_lineage.md)
