# Static Firm-Level Tightness (2019-H2)

This note documents how the dataset `data/clean/firm_tightness_static.csv` is produced.  The file contains **one row per company** with the variable `tight_wavg`, a head-count-weighted measure of labour-market tightness that is *fixed in time* at the firm’s **2019-H2 occupational composition**.

--------------------------------------------------------------------
1  Source data
--------------------------------------------------------------------

| Data file | Description |
|-----------|-------------|
| `data/clean/linkedin_panel.parquet` | Half-year spells of LinkedIn workers (built by `py/build_linkedin_panel_duckdb.py`). |
| `data/raw/oews/processed_data/tight_occ_msa_y.csv` | OEWS occupation-by-CBSA tightness metric for 2019. |

--------------------------------------------------------------------
2  Firm × SOC tightness lookup
--------------------------------------------------------------------
Script: **`py/build_firm_occ_tightness.py`**

1. Collapse LinkedIn to 2019-H2 `company × SOC-4 × CBSA`, keep metros with ≥ 3 heads.  → `firm_occ_msa_heads_2019H2.csv`.
2. Head-count-weighted average of OEWS tightness across the remaining metros.  → `tight_wavg_lookup.csv` (company × SOC).
3. Attach the lookup to every half-year of LinkedIn data.  → `firm_occ_panel_enriched.csv` (company × SOC × yh).

--------------------------------------------------------------------
3  Static firm-level tightness
--------------------------------------------------------------------
Script: **`py/build_firm_panel.py`** (2025-07 revision)

1. Filter the occupation panel to `yh == 4039` (2019-H2).
2. For each company, compute a head-count-weighted mean of `tight_wavg` across SOCs (ignoring NaNs):

```python
np.average(tight, weights=heads)
```

3. Persist the result as `data/clean/firm_tightness_static.csv`.
4. Merge the same value into every half-year row of `firm_panel_enriched.csv` so regressions already have the variable.

--------------------------------------------------------------------
4  Re-run instructions
--------------------------------------------------------------------

```bash
# Build occupation-level panel and lookup (only if inputs changed)
python py/build_firm_occ_tightness.py

# Build firm-level panel *and* the static tightness CSV
python py/build_firm_panel.py   # writes firm_tightness_static.csv
```

--------------------------------------------------------------------
5  Schema of `firm_tightness_static.csv`
--------------------------------------------------------------------

| Column | Type   | Description |
|--------|--------|-------------|
| companyname | string  | Lower-cased firm name (pipeline key). |
| tight_wavg  | float64 | Head-count-weighted OEWS tightness, 2019-H2 weights. |

Rows (latest run): 4 136 firms.  About 11 % of firms have `tight_wavg = .` because none of their 2019-H2 occupations matched an OEWS figure; handle these missing values as appropriate.
