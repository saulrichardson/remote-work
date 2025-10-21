# Geographic Expansion Analysis: Approach Comparison

## Overview
There are multiple existing scripts for geographic expansion analysis, plus our new implementation. Here's a comparison:

## Existing Approaches

### 1. `firm_geographic_expansion.do` (Original)
- **Data Source**: Merges firm_panel.dta with firm_geographic_expansion.csv
- **Period**: Uses FULL panel but expects geo data only for post-period
- **Pre-period handling**: Calculates pre-period mean (which would be 0 or missing)
- **Method**: ivreghdfe with firm and time FE
- **Key feature**: Exports to CSV with first-stage F-stats

### 2. `firm_geographic_expansion_simple.do` 
- **Data Source**: Uses pre-merged firm_panel_with_geo_analysis.csv
- **Period**: Works with whatever is in the merged file (likely post-only)
- **Pre-period handling**: Not explicitly handled
- **Method**: ivreghdfe with firm and time FE
- **Key feature**: Includes robustness checks (intensive/extensive margin)

### 3. `firm_geographic_expansion_analysis.do`
- **Data Source**: Merges firm_panel.dta with firm_geographic_expansion.csv
- **Period**: Full panel with merge indicator
- **Pre-period handling**: Uses merge indicator to track coverage
- **Method**: ivreghdfe following firm_scaling.do framework
- **Key feature**: More diagnostic checks

## Our New Implementations

### 4. Our Initial Approach (basic_iv.do, etc.)
- **Data Source**: firm_panel_with_geo_analysis.csv (post-period only, 15,709 obs)
- **Period**: POST-ONLY
- **Result**: var3 coefficient = -0.157 (negative effect)

### 5. Our Full Panel Approach (geographic_expansion_full_iv.do)
- **Data Source**: firm_panel_full_with_geography.csv (41,980 obs)
- **Period**: FULL panel with pre-period set to 0
- **Without year FE**: var3 = +0.453 (positive - likely mechanical)
- **With year FE**: var3 = -0.149 (negative - consistent)

## Key Decision Points

### Option A: Post-Period Only
**Rationale**: Geographic expansion is undefined/zero pre-2019 by construction
- Clean interpretation
- Avoids mechanical correlations
- Matches actual data availability
- **Result**: -15.7pp effect

### Option B: Full Panel with Pre=0
**Rationale**: Maintains consistency with other analyses
- Requires year FE to avoid mechanical positive bias
- Allows for pre-trend testing (though meaningless here)
- **Result**: -14.9pp effect with year FE

### Option C: Full Panel, Drop Pre-Period Geo Variable
**Rationale**: Use full panel for controls but only post-period geo outcome
- This is what firm_geographic_expansion.do appears to do
- Merges post-only geo data with full panel

## Recommendation

The existing `firm_geographic_expansion.do` uses **Option C**: Full panel for regression framework but geographic expansion data only exists post-period. This makes sense because:

1. Maintains full panel structure for proper identification
2. Doesn't artificially set pre-period values 
3. Allows the regression to use full variation in treatment/controls

The key insight: The geographic expansion CSV from Python should only contain post-2019 observations (when the metric is defined), but the regression should use the full panel structure.

## Code Comparison

### Existing Approach (firm_geographic_expansion.do):
```stata
use "$processed_data/firm_panel.dta", clear  // Full panel
merge 1:1 companyname yh using `geo_expansion', keep(1 3)  // Post-only geo data
```

### Our Approach Should Be:
```stata
use "$processed_data/firm_panel.dta", clear  // Full panel
keep if covid == 1  // Post-only for geographic outcome
merge with geographic_expansion_metrics
```

OR better:
```stata
use "$processed_data/firm_panel.dta", clear  // Full panel
merge 1:1 companyname yh using geographic_expansion_post_only.csv, keep(1 3)
// Run regression on full panel, geo outcome only defined post-period
```