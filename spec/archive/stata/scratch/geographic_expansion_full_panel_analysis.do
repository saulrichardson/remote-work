// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

/*
================================================================================
GEOGRAPHIC EXPANSION ANALYSIS - FULL PANEL WITH 5% THRESHOLD
================================================================================
Tests whether remote work enables firms to hire beyond traditional geographic 
footprints using full panel (41,980 obs).

Legacy locations defined as: ≥100 employees OR ≥5% of firm (updated from 10%)
Pre-period geographic expansion set to 0 by definition.
================================================================================
*/

clear all
set more off

// Load full panel with geographic expansion metrics
import delimited "data/processed/firm_panel_full_with_geography.csv", clear

di _n(2) "========================================"
di "GEOGRAPHIC EXPANSION ANALYSIS"
di "Full Panel with 5% Threshold"
di "========================================"
di "Total observations: " _N

// ============================================================================
// 1. SUMMARY STATISTICS
// ============================================================================

di _n(2) "=== SUMMARY STATISTICS ==="

// By period
tabstat share_new_geo, by(covid) stat(mean sd min p25 p50 p75 max n)

// Check how many firms have geographic expansion data
count if !missing(share_new_geo)
local n_with_geo = r(N)
di "Observations with geographic data: " `n_with_geo'

// Treatment distribution
tab covid var3 if !missing(share_new_geo)

// ============================================================================
// 2. MAIN REGRESSION - FULL PANEL WITH YEAR FE
// ============================================================================

di _n(2) "=== FULL PANEL ANALYSIS ==="

// Create year variable (check if exists first)
capture drop year
gen year = int(yh_int/2)

// Check sample sizes
count if !missing(share_new_geo, var3, var5, var4)
local n_reg = r(N)
di "Observations in regression: " `n_reg'

// OLS with year FE
di _n "OLS with Year Fixed Effects:"
reg share_new_geo var3 var5 var4 i.year, robust
estimates store ols_full

// Store OLS results
local b_ols = _b[var3]
local se_ols = _se[var3]
local p_ols = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))

// IV with year FE  
di _n "IV (2SLS) with Year Fixed Effects:"
ivreg2 share_new_geo (var3 var5 = var6 var7) var4 i.year, robust first

estimates store iv_full

// Store IV results
local b_iv = _b[var3]
local se_iv = _se[var3]
local p_iv = 2*normal(-abs(_b[var3]/_se[var3]))
local rkf = e(rkf)

// ============================================================================
// 3. POST-PERIOD ONLY FOR COMPARISON
// ============================================================================

di _n(2) "=== POST-PERIOD ONLY (for comparison) ==="

preserve
keep if covid == 1
count
local n_post = r(N)
di "Post-period observations: " `n_post'

// Simple IV without year FE
di _n "IV (Post-period only):"
ivreg2 share_new_geo (var3 var5 = var6 var7) var4, robust

local b_post = _b[var3]
local se_post = _se[var3]
local p_post = 2*normal(-abs(_b[var3]/_se[var3]))

restore

// ============================================================================
// 4. RESULTS SUMMARY
// ============================================================================

di _n(2) "========================================"
di "RESULTS SUMMARY (5% threshold)"
di "========================================"

di _n "Full Panel with Year FE:"
di "  OLS coefficient: " %7.4f `b_ols' " (SE=" %6.4f `se_ols' ", p=" %5.3f `p_ols' ")"
di "  IV coefficient:  " %7.4f `b_iv'  " (SE=" %6.4f `se_iv'  ", p=" %5.3f `p_iv' ")"
di "  KP F-stat: " %6.2f `rkf'

di _n "Post-Period Only:"
di "  IV coefficient:  " %7.4f `b_post' " (SE=" %6.4f `se_post' ", p=" %5.3f `p_post' ")"

// Interpretation
di _n "INTERPRETATION:"
if `p_iv' < 0.10 {
    local effect = `b_iv' * 100
    if `b_iv' > 0 {
        di "Remote firms have " %4.1f abs(`effect') " percentage points MORE"
        di "hires in new geographies (beyond 5% threshold locations)."
    }
    else {
        di "Remote firms have " %4.1f abs(`effect') " percentage points FEWER"
        di "hires in new geographies (beyond 5% threshold locations)."
    }
}
else {
    di "No statistically significant effect at 10% level."
}

// ============================================================================
// 5. ROBUSTNESS: CHECK DIFFERENT SAMPLES
// ============================================================================

di _n(2) "=== ROBUSTNESS CHECKS ==="

// Check means by treatment status in post-period
di _n "Mean geographic expansion by treatment (post-period):"
tabstat share_new_geo if covid==1, by(var3) stat(mean sd n)

// Distribution check
di _n "Distribution of geographic expansion (post-period):"
sum share_new_geo if covid==1, detail
sum share_new_geo if covid==1 & var3==0, detail
sum share_new_geo if covid==1 & var3==1, detail

di _n(2) "========================================"
di "ANALYSIS COMPLETE"
di "Threshold: 100 employees OR 5% of firm"
di "========================================"

exit