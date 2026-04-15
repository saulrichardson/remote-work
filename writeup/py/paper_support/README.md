# Paper Support Scripts

This folder holds the narrow support code for the active repo-owned paper lane
when that code does not belong in upstream data construction.

## What Lives Here

### `paper_asset_contract.json`

The machine-readable contract for the in-scope active manuscript lane.

It records:

- active in-scope manuscript assets
- excluded active manuscript assets
- raw outputs, upstream inputs, and builders for each asset
- generated docs tied to that contract

### `paper_assets.py`

Loader and parsing helpers for the asset contract and `main.tex` references.

### `paper_lane.py`

Internal orchestration helper used by the active grouped commands to:

- regenerate contract-derived docs
- run the active table-side Stata specs
- run the active figure-side Stata specs
- run the active table builders
- run the active figure builders

### `table_of_means.py`

Builds the descriptive summary-statistics table.

Inputs:

- [`../../data/clean/firm_panel.dta`](../../data/clean/firm_panel.dta)
- [`../../data/clean/user_panel_precovid.dta`](../../data/clean/user_panel_precovid.dta)
- [`../../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv`](../../results/raw/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv)

Output:

- [`../../results/cleaned/tex/table_of_means.tex`](../../results/cleaned/tex/table_of_means.tex)

## Contract-Derived Docs

The active grouped commands regenerate:

- [`../../docs/main_tex_assets.md`](../../docs/main_tex_assets.md)
- [`../../docs/paper_table_lineage.md`](../../docs/paper_table_lineage.md)
- [`../../docs/figure_lineage.md`](../../docs/figure_lineage.md)
- [`../../writeup/tex/main_assets_preview.tex`](../../writeup/tex/main_assets_preview.tex)

## Placement Rule

If a helper here grows into a real domain family, move it into a dedicated
subdirectory under [`../`](../).
