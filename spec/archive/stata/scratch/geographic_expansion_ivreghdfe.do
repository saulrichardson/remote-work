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
GEOGRAPHIC EXPANSION ANALYSIS - IVREGHDFE SPECIFICATION
================================================================================
Full panel analysis with 5% threshold for legacy locations
Using ivreghdfe to match other specifications in the project
Legacy: ≥100 employees OR ≥5% of firm in 2019-H2
================================================================================
*/

clear all
set more off

// Load data
import delimited "data/processed/firm_panel_full_with_geography.csv", clear

di _n "=========================================="
di "GEOGRAPHIC EXPANSION - IVREGHDFE ANALYSIS"
di "=========================================="
di "N = " _N

// Summary by period
di _n "Summary by period:"
tabstat share_new_geo, by(covid) stat(mean sd n) format(%9.4f)

// Create firm_id if not numeric
// capture confirm numeric variable firm_id
// if _rc {
//     encode companyname, gen(firm_id)
//     drop firm_id
//     rename firm_id_num firm_id
// }

encode companyname, gen(firm_id)

// ============================================================================
// MAIN SPECIFICATION: FULL PANEL WITH FIRM AND TIME FE
// ============================================================================

di _n "=========================================="
di "MAIN IV SPECIFICATION (ivreghdfe)"
di "=========================================="

// This matches the specification in firm_scaling.do and other analyses
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id) first savefirst

// Store main results
local b = _b[var3]
local se = _se[var3]
local t = `b'/`se'
local p = 2*ttail(e(df_r), abs(`t'))
local ci_low = `b' - 1.96*`se'
local ci_high = `b' + 1.96*`se'
local rkf = e(rkf)
local N = e(N)

di _n "KEY RESULT:"
di "==========="
di "Coefficient on var3 (remote × covid): " %7.4f `b'
di "Standard error: " %7.4f `se'
di "95% CI: [" %7.4f `ci_low' ", " %7.4f `ci_high' "]"
di "P-value: " %6.4f `p'
di "KP F-stat: " %6.2f `rkf'
di "N: " `N'

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
// ALTERNATIVE 1: OLS FOR COMPARISON
// ============================================================================

di _n "=========================================="
di "OLS SPECIFICATION (for comparison)"
di "=========================================="

reghdfe share_new_geo var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

di _n "OLS coefficient: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

// ============================================================================
// ALTERNATIVE 2: POST-PERIOD ONLY 
// ============================================================================

di _n "=========================================="
di "POST-PERIOD ONLY (Robustness Check)"
di "=========================================="

preserve
keep if covid == 1
di "N = " _N

// Check if enough variation exists
qui sum share_new_geo
if r(sd) > 0 {
    ivreghdfe share_new_geo (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    
    di _n "Post-period coefficient: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"
    di "KP F-stat: " %6.2f e(rkf)
}
else {
    di "No variation in outcome - skipping regression"
}

restore

// ============================================================================
// FIRST STAGE DIAGNOSTICS
// ============================================================================

di _n "=========================================="
di "FIRST STAGE DIAGNOSTICS"
di "=========================================="

// Restore first stage for var3
estimates restore _ivreg2_var3
di _n "First stage for var3:"
di "var6 coefficient: " %7.4f _b[var6] " (SE = " %7.4f _se[var6] ")"
di "var7 coefficient: " %7.4f _b[var7] " (SE = " %7.4f _se[var7] ")"

// Restore first stage for var5
estimates restore _ivreg2_var5
di _n "First stage for var5:"
di "var6 coefficient: " %7.4f _b[var6] " (SE = " %7.4f _se[var6] ")"
di "var7 coefficient: " %7.4f _b[var7] " (SE = " %7.4f _se[var7] ")"

// ============================================================================
// HETEROGENEITY BY TREATMENT INTENSITY (POST-PERIOD)
// ============================================================================

di _n "=========================================="
di "HETEROGENEITY ANALYSIS"
di "=========================================="

preserve
keep if covid == 1

// Summary by exact var3 values
di _n "Mean share_new_geo by var3 value (post-period):"
tabstat share_new_geo, by(var3) stat(mean sd n) format(%9.4f) nototal

// Check if remote firms (var3==1) exist and have different outcomes
qui sum share_new_geo if var3 == 0
local mean_control = r(mean)
qui sum share_new_geo if var3 == 1
local mean_treated = r(mean)
local diff = `mean_treated' - `mean_control'

di _n "Raw difference (var3=1 vs var3=0): " %6.4f `diff'
di "(Before controlling for other factors)"

restore

di _n "=========================================="
di "ANALYSIS COMPLETE"
di "=========================================="
di "Specification: ivreghdfe with firm and time FE"
di "Threshold: 100 employees OR 5% of firm"
di "=========================================="

exit
