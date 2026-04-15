# `writeup/py/firm_scaling/`

This directory holds the active firm-side table builders for the repo-owned
paper lane.

These builders render cleaned LaTeX fragments from firm-side empirical exports.

## Active Builders

- `03_firm_scaling_crunchbase_fundraising_core4.py`
- `04_firm_scaling_precovid.py`
- `14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd.py`
- `15_firm_scaling_location_ratios.py`

## Main Inputs

- `results/raw/03_firm_scaling_crunchbase_fundraising_core4/`
- `results/raw/04_firm_scaling_precovid/`
- `results/raw/14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd/`
- `results/raw/15_firm_scaling_location_ratios/`

## How To Run

Examples:

```bash
./bin/project-python writeup/py/firm_scaling/04_firm_scaling_precovid.py
./bin/project-python writeup/py/firm_scaling/03_firm_scaling_crunchbase_fundraising_core4.py
```

Or:

```bash
make paper
```

## Related Docs

- [`../../../docs/core_specs.md`](../../../docs/core_specs.md)
- [`../../../docs/crunchbase_workflow.md`](../../../docs/crunchbase_workflow.md)
- [`../../../docs/paper_table_lineage.md`](../../../docs/paper_table_lineage.md)
- [`../README.md`](../README.md)
