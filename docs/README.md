# Documentation Index

This directory contains the runbooks and empirical notes for the active
repo-owned paper lane.

The documentation is now organized to answer three different questions:

1. How do I run the repo?
2. How does data move from source boundaries to final paper assets?
3. What are the main empirical designs behind the active paper results?

## Start Here

### 1. Technical run order

- [`../README.md`](../README.md)
  - top-level repo map and the three public commands
- [`local_runbook.md`](local_runbook.md)
  - detailed technical runbook from repo root commands to logs and outputs
- [`upstream_data_ontology.md`](upstream_data_ontology.md)
  - exact map of source-boundary inputs, accepted local boundaries, generated datasets, and
    downstream handoffs

### 2. Empirical design

- [`core_specs.md`](core_specs.md)
  - high-level empirical overview of the active user-productivity, firm-scaling,
    event-study, Crunchbase, vacancy, and remote-hire designs

### 3. Manuscript asset ownership

- [`main_tex_assets.md`](main_tex_assets.md)
  - active `main.tex` inventory, path types, and explicit exclusions
- [`paper_table_lineage.md`](paper_table_lineage.md)
  - table-by-table lineage from upstream inputs to final LaTeX fragments
- [`figure_lineage.md`](figure_lineage.md)
  - figure-by-figure lineage from cleaned data or Stata exports to final PNGs

## Workflow-Specific Runbooks

- [`crunchbase_workflow.md`](crunchbase_workflow.md)
  - the active Crunchbase funding branch from raw files to final paper assets
- [`postings_equity_workflow.md`](postings_equity_workflow.md)
  - the active postings-description equity branch, including the accepted OpenAI
    Batch boundary
- [`static_firm_tightness.md`](static_firm_tightness.md)
  - background on the static firm tightness measure

## Research Notes

These files are useful context but are not the primary operational runbook:

- `binsreg_prompt.md`
- `firm_age_productivity_visuals.md`
- `geographic_expansion_approach_comparison.md`
- `remote_shift_analysis_plan.md`
- `threeway_results_summary.md`
- `tightness_metric_comparison.md`

## How These Docs Fit Together

If you want the shortest path to understanding the repo:

1. read [`local_runbook.md`](local_runbook.md)
2. read [`core_specs.md`](core_specs.md)
3. use [`main_tex_assets.md`](main_tex_assets.md) plus the lineage docs to map the
   empirical families onto the active manuscript assets
