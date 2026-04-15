# `writeup/py/startup_cutoff/`

This directory holds the active startup-cutoff figure builders.

## Active Builders

- `03_startup_cutoff_bars_total_contributions_q100.py`
- `04_startup_cutoff_bars_growth_rate_we.py`

## Upstream Inputs

- [`../../../results/raw/03_startup_cutoff_bars_total_contributions_q100/user_productivity/consolidated_results.csv`](../../../results/raw/03_startup_cutoff_bars_total_contributions_q100/user_productivity/consolidated_results.csv)
- [`../../../results/raw/04_startup_cutoff_bars_growth_rate_we/firm_scaling/consolidated_results.csv`](../../../results/raw/04_startup_cutoff_bars_growth_rate_we/firm_scaling/consolidated_results.csv)

Owning Stata specs:

- [`../../../spec/stata/figures/03_startup_cutoff_bars_total_contributions_q100.do`](../../../spec/stata/figures/03_startup_cutoff_bars_total_contributions_q100.do)
- [`../../../spec/stata/figures/04_startup_cutoff_bars_growth_rate_we.do`](../../../spec/stata/figures/04_startup_cutoff_bars_growth_rate_we.do)

## How To Run

```bash
./bin/project-python writeup/py/startup_cutoff/03_startup_cutoff_bars_total_contributions_q100.py
./bin/project-python writeup/py/startup_cutoff/04_startup_cutoff_bars_growth_rate_we.py
```

Or:

```bash
make paper
```
