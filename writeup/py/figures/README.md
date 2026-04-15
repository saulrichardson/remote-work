# Figure Scripts

This folder holds the active figure builders that render manuscript-facing PNGs.

## Two Figure Modes

### Descriptive figures

These read canonical cleaned datasets directly from `data/clean/`.

Current active examples:

- [`01_firm_age_lt100_remote.py`](01_firm_age_lt100_remote.py)
- [`02_firm_teleworkable_remote.py`](02_firm_teleworkable_remote.py)

Shared inputs:

- [`../../../data/clean/firm_panel.dta`](../../../data/clean/firm_panel.dta)
- [`../../../data/clean/user_panel_precovid.dta`](../../../data/clean/user_panel_precovid.dta)

### Estimation-driven figures

These read machine-readable exports from `results/raw/`.

This covers:

- event-study figures
- vacancy event-study figures
- full-remote event-study figures
- Crunchbase event-study figure
- engineer / non-engineer IRFs

## How To Run

Examples:

```bash
./bin/project-python writeup/py/figures/01_firm_age_lt100_remote.py
./bin/project-python writeup/py/figures/02_firm_teleworkable_remote.py
./bin/project-python writeup/py/figures/panelB_fullremote_engineer.py
./bin/project-python writeup/py/figures/panelB_fullremote_nonengineer.py
```

Or run the grouped paper-output phase:

```bash
make paper
```

## Output Locations

- non-IRF figures -> [`../../../results/cleaned/figures/`](../../../results/cleaned/figures/)
- IRF panels -> [`../../../results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/`](../../../results/cleaned/irfs/user_irfs_eng_vs_noneng_remote_hybrid/)

## Related Docs

- [`../../../docs/main_tex_assets.md`](../../../docs/main_tex_assets.md)
- [`../../../docs/figure_lineage.md`](../../../docs/figure_lineage.md)
