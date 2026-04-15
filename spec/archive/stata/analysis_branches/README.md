# `spec/archive/stata/analysis_branches/`

This subtree holds Stata analysis branches that remain part of the repository but are not part of
the active paper-critical lane driven by the current Overleaf `main.tex`.

The intent of the partition is simple:

- keep `spec/stata/` top level focused on the paper-owned specs and exporters that are actually
  used by the current `make paper-specs` and `make paper-figure-specs` targets
- keep non-paper analysis in `spec/archive/stata/analysis_branches/` so it remains available without
  crowding the active paper surface

## Subdirectories

- `llm_equity/`
  - LLM-equity and equity-compensation analysis branches
- `horse_races/`
  - horse-race comparison specifications
- `crunchbase_followups/`
  - Crunchbase fundraising follow-ups and side branches beyond the paper-critical core specs
- `github_validation/`
  - GitHub validation analysis branches
- `geography_demographics/`
  - geography, demographic, sales, and related spatial variants
- `cutoff_size_variants/`
  - size and cutoff variants that are not part of the current `main.tex` paper lane
- `legacy_variants/`
  - older productivity/mechanism variants and other non-paper top-level scripts that were moved out
    of the active surface

## What stays at `spec/stata/`

Only the paper-critical surface:

- the Stata specs mapped to the active `../Results/Tables/...` inputs in `main.tex`
- the figure exporters mapped to the active `../Results/Figures/...` inputs in `main.tex`
- `_bootstrap.do`
- the top-level `README.md`
- `support/` for active shared helpers used by the paper-critical specs
