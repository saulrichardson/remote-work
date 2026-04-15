# `writeup/archive/py/`

This tree holds cleaned-output Python builders that remain part of the repository but are not part
of the active paper-owned build lane.

The partition is intentional:

- [`../../py/`](../../py/)
  - active paper-owned table builders, figure builders, and support modules
- `archive/`
  - older wrapper layers and retired cleaned-output scripts
- `firm_scaling/`, `user_productivity/`, `user_hire/`, `startup_cutoff/`, `figures/`
  - archived domain-specific builders that are currently outside the active paper lane
- `llm_equity/`, `firm_sales/`, `scratch/`
  - non-paper branches and exploratory formatting code

Nothing here was deleted. These files were moved out of `writeup/py/` so the active paper-facing
surface is easier to follow and rerun.
