# `writeup/py/user_productivity/`

This directory holds the active user-productivity table builders for the
repo-owned paper lane.

These builders are downstream of:

- user-side empirical exports in [`../../../results/raw/`](../../../results/raw/)
- the active user-productivity Stata owners in [`../../../spec/stata/tables/`](../../../spec/stata/tables/)

## Active Builders

- `01_user_productivity_precovid_total_ols_single.py`
- `02_user_productivity_precovid_total_iv_single.py`
- `05_user_mechanisms_keep_remote_precovid.py`
- `06_user_wage_fe_variants_precovid_log_salary.py`
- `07_user_productivity_fr_focus_precovid.py`
- `08_user_productivity_top_metros_firmbyuser.py`
- `09_user_productivity_traits_dual_precovid_ols.py`
- `10_user_productivity_precovid_nonsoftware.py`
- `11_first_stage_summary.py`
- `11_user_productivity_precovid_restricted.py`
- `12_user_productivity_precovid_stayer_table3.py`
- `13_user_productivity_precovid_industry_hqstate_shocks.py`

## Important Input Patterns

- most builders read `results/raw/<asset>/...`
- `05_user_mechanisms_keep_remote_precovid.py` also uses the upstream equity panel
- `11_first_stage_summary.py` is downstream-only and summarizes already-exported
  first-stage results

## How To Run

Examples:

```bash
./bin/project-python writeup/py/user_productivity/01_user_productivity_precovid_total_ols_single.py
./bin/project-python writeup/py/user_productivity/11_first_stage_summary.py
./bin/project-python writeup/py/user_productivity/05_user_mechanisms_keep_remote_precovid.py --variant precovid
```

Or run the grouped paper-output phase:

```bash
make paper
```

## Related Docs

- [`../../../docs/core_specs.md`](../../../docs/core_specs.md)
- [`../../../docs/paper_table_lineage.md`](../../../docs/paper_table_lineage.md)
- [`../README.md`](../README.md)
