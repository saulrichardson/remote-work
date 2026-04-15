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
GEOGRAPHIC EXPANSION ANALYSIS - FINAL VERSION
================================================================================
Full panel analysis with 5% threshold for legacy locations
Legacy: ≥100 employees OR ≥5% of firm in 2019-H2
================================================================================
*/

clear all
set more off

// Load data
import delimited "data/processed/firm_panel_full_with_geography.csv", clear

di _n "=========================================="
di "GEOGRAPHIC EXPANSION - FINAL RESULTS"
di "=========================================="
di "N = " _N

// Summary by period
di _n "Summary by period:"
tabstat share_new_geo, by(covid) stat(mean sd n) format(%9.4f)

// Create year variable
capture drop year
gen year = int(yh_int/2)

// ============================================================================
// MAIN IV REGRESSION WITH YEAR FE
// ============================================================================

di _n "=========================================="
di "IV REGRESSION (Full Panel with Year FE)"
di "=========================================="

ivreg2 share_new_geo (var3 var5 = var6 var7) var4 i.year, robust

// Store and display key result
local b = _b[var3]
local se = _se[var3]
local t = `b'/`se'
local p = 2*normal(-abs(`t'))
local ci_low = `b' - 1.96*`se'
local ci_high = `b' + 1.96*`se'

di _n "KEY RESULT:"
di "==========="
di "Coefficient on var3 (remote × covid): " %7.4f `b'
di "Standard error: " %7.4f `se'
di "95% CI: [" %7.4f `ci_low' ", " %7.4f `ci_high' "]"
di "P-value: " %6.4f `p'

di _n "Interpretation:"
di "Remote firms have " %4.1f abs(`b'*100) " percentage points " _continue
if `b' > 0 {
    di "MORE hires in new geographies"
}
else {
    di "FEWER hires in new geographies"
}
di "(Locations beyond those with ≥100 employees or ≥5% of firm in 2019-H2)"

// ============================================================================
// ROBUSTNESS: POST-PERIOD ONLY
// ============================================================================

di _n "=========================================="
di "ROBUSTNESS CHECK: Post-Period Only"
di "=========================================="

preserve
keep if covid == 1
di "N = " _N

ivreg2 share_new_geo (var3 var5 = var6 var7) var4, robust

di _n "Post-period coefficient: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

restore

// ============================================================================
// HETEROGENEITY BY TREATMENT INTENSITY
// ============================================================================

di _n "=========================================="
di "Mean Share New Geo by Treatment Level"
di "=========================================="

preserve
keep if covid == 1

// Group var3 into categories for clearer presentation
gen treatment_group = .
replace treatment_group = 0 if var3 == 0
replace treatment_group = 1 if var3 > 0 & var3 <= 0.5
replace treatment_group = 2 if var3 > 0.5 & var3 <= 1

label define treat_lab 0 "No Remote" 1 "Partial Remote" 2 "Full Remote"
label values treatment_group treat_lab

di _n "Average share in new geography by treatment intensity:"
tabstat share_new_geo, by(treatment_group) stat(mean sd n) format(%9.4f)

// Also show raw var3 values
di _n "By exact var3 values (post-period):"
tabstat share_new_geo, by(var3) stat(mean n) format(%9.4f)

restore

di _n "=========================================="
di "ANALYSIS COMPLETE"
di "=========================================="

exit