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
THREE-WAY SUBSTITUTION ANALYSIS: REMOTE vs GEOGRAPHIC EXPANSION
================================================================================
Tests whether remote work substitutes for or complements geographic expansion
by decomposing hiring into three categories:
1. Legacy MSA - traditional office locations (2019-H2 baseline)
2. New MSA - new physical locations
3. Remote - workers without MSA designation

Key hypothesis: If remote substitutes for geographic expansion, we should see:
- Negative effect on new MSA hiring (confirmed: -15pp)
- Positive effect on remote hiring (offsetting)
- Near-zero effect on total dispersion (net neutral)
================================================================================
*/

clear all
set more off

// Load data
import delimited "data/processed/firm_panel_threeway_geography.csv", clear

di _n "=========================================="
di "THREE-WAY HIRING SUBSTITUTION ANALYSIS"
di "=========================================="
di "N = " _N

// Create firm_id if needed
capture drop firm_id_temp
encode companyname, gen(firm_id_temp)

// ============================================================================
// SUMMARY STATISTICS
// ============================================================================

di _n "=========================================="
di "SUMMARY BY PERIOD"
di "=========================================="

di _n "Pre-COVID (2019) vs Post-COVID (2020+) Averages:"
tabstat share_legacy_msa share_new_msa share_remote total_dispersion, ///
    by(covid) stat(mean sd n) format(%9.4f) nototal

// Check treatment variation
di _n "Post-period variation by treatment:"
preserve
keep if covid == 1
tabstat share_legacy_msa share_new_msa share_remote total_dispersion, ///
    by(var3) stat(mean sd n) format(%9.4f) nototal
restore

// ============================================================================
// MAIN SPECIFICATIONS: THREE PARALLEL IV REGRESSIONS
// ============================================================================

di _n _dup(70) "="
di "MAIN IV REGRESSIONS: DECOMPOSING THE GEOGRAPHIC EFFECT"
di _dup(70) "="

// Store results for comparison
matrix results = J(3, 5, .)
matrix rownames results = "New_MSA" "Remote" "Total_Dispersion"
matrix colnames results = "Coefficient" "SE" "P_value" "CI_Low" "CI_High"

// --------------------------------
// 1. NEW MSA HIRING (Physical expansion only)
// --------------------------------
di _n "1. NEW MSA HIRING (Physical Geographic Expansion)"
di _dup(50) "-"

ivreghdfe share_new_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp) first savefirst

// Store results
matrix results[1,1] = _b[var3]
matrix results[1,2] = _se[var3]
local t = _b[var3]/_se[var3]
matrix results[1,3] = 2*ttail(e(df_r), abs(`t'))
matrix results[1,4] = _b[var3] - 1.96*_se[var3]
matrix results[1,5] = _b[var3] + 1.96*_se[var3]

local b1 = _b[var3]
local se1 = _se[var3]
local p1 = 2*ttail(e(df_r), abs(`b1'/`se1'))
local rkf1 = e(rkf)

di _n "Result: " %7.4f `b1' " (SE = " %7.4f `se1' ", p = " %6.4f `p1' ")"
di "KP F-stat: " %6.2f `rkf1'

// --------------------------------
// 2. REMOTE HIRING
// --------------------------------
di _n "2. REMOTE HIRING"
di _dup(50) "-"

ivreghdfe share_remote (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

// Store results
matrix results[2,1] = _b[var3]
matrix results[2,2] = _se[var3]
local t = _b[var3]/_se[var3]
matrix results[2,3] = 2*ttail(e(df_r), abs(`t'))
matrix results[2,4] = _b[var3] - 1.96*_se[var3]
matrix results[2,5] = _b[var3] + 1.96*_se[var3]

local b2 = _b[var3]
local se2 = _se[var3]
local p2 = 2*ttail(e(df_r), abs(`b2'/`se2'))
local rkf2 = e(rkf)

di _n "Result: " %7.4f `b2' " (SE = " %7.4f `se2' ", p = " %6.4f `p2' ")"
di "KP F-stat: " %6.2f `rkf2'

// --------------------------------
// 3. TOTAL DISPERSION (New MSA + Remote)
// --------------------------------
di _n "3. TOTAL DISPERSION (New MSA + Remote)"
di _dup(50) "-"

ivreghdfe total_dispersion (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

// Store results
matrix results[3,1] = _b[var3]
matrix results[3,2] = _se[var3]
local t = _b[var3]/_se[var3]
matrix results[3,3] = 2*ttail(e(df_r), abs(`t'))
matrix results[3,4] = _b[var3] - 1.96*_se[var3]
matrix results[3,5] = _b[var3] + 1.96*_se[var3]

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local rkf3 = e(rkf)

di _n "Result: " %7.4f `b3' " (SE = " %7.4f `se3' ", p = " %6.4f `p3' ")"
di "KP F-stat: " %6.2f `rkf3'

// ============================================================================
// RESULTS COMPARISON TABLE
// ============================================================================

di _n _dup(70) "="
di "RESULTS COMPARISON: DECOMPOSING GEOGRAPHIC HIRING"
di _dup(70) "="

matlist results, format(%9.4f) lines(oneline) ///
    title("Treatment Effect on Hiring Shares (var3 coefficient)")

// Calculate sum and substitution metrics
local sum_new_remote = `b1' + `b2'
local substitution_rate = -`b2' / `b1' * 100

di _n "Key Metrics:"
di _dup(50) "-"
di "Sum of New MSA + Remote effects: " %7.4f `sum_new_remote'
di "Should equal Total Dispersion: " %7.4f `b3'
di "Difference: " %7.4f abs(`sum_new_remote' - `b3')

di _n "Substitution Analysis:"
di _dup(50) "-"
if `b1' < 0 & `b2' > 0 {
    di "✓ Evidence of substitution: New MSA ↓, Remote ↑"
    di "  Substitution rate: " %5.1f `substitution_rate' "%"
    di "  (Remote offsets " %5.1f `substitution_rate' "% of new MSA decline)"
}
else if `b1' < 0 & `b2' < 0 {
    di "✗ No substitution: Both New MSA and Remote decline"
    di "  This suggests concentration in legacy locations"
}
else if `b1' > 0 & `b2' > 0 {
    di "◊ Complementarity: Both New MSA and Remote increase"
}
else {
    di "? Mixed pattern requiring further investigation"
}

// ============================================================================
// ADDITIONAL TEST: LEGACY MSA CONCENTRATION
// ============================================================================

di _n _dup(70) "="
di "LEGACY MSA CONCENTRATION TEST"
di _dup(70) "="

ivreghdfe share_legacy_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local b_legacy = _b[var3]
local se_legacy = _se[var3]
local p_legacy = 2*ttail(e(df_r), abs(`b_legacy'/`se_legacy'))

di _n "Effect on Legacy MSA share: " %7.4f `b_legacy' ///
    " (SE = " %7.4f `se_legacy' ", p = " %6.4f `p_legacy' ")"

if `b_legacy' > 0 {
    di "→ Remote firms CONCENTRATE in traditional office locations"
}
else if `b_legacy' < 0 {
    di "→ Remote firms DISPERSE from traditional office locations"
}

// Verify shares sum to zero
local sum_all = `b_legacy' + `b1' + `b2'
di _n "Verification (should be ~0): Legacy + New MSA + Remote = " %7.4f `sum_all'

// ============================================================================
// ROBUSTNESS: POST-PERIOD ONLY
// ============================================================================

di _n _dup(70) "="
di "ROBUSTNESS: POST-PERIOD ONLY"
di _dup(70) "="

preserve
keep if covid == 1
di "N = " _N

di _n "Post-period New MSA:"
ivreghdfe share_new_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)
di "Coefficient: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

di _n "Post-period Remote:"
ivreghdfe share_remote (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)
di "Coefficient: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

di _n "Post-period Total Dispersion:"
ivreghdfe total_dispersion (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)
di "Coefficient: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

restore

// ============================================================================
// INTERPRETATION SUMMARY
// ============================================================================

di _n _dup(70) "="
di "INTERPRETATION SUMMARY"
di _dup(70) "="

di _n "Main Finding:"
if `b1' < 0 & abs(`b2') < abs(`b1')/2 {
    di "Remote work does NOT fully substitute for geographic expansion."
    di "The decline in new MSA hiring (" %5.2f `b1'*100 "pp) is much larger"
    di "than any increase in remote hiring (" %+5.2f `b2'*100 "pp)."
    di _n "This suggests remote-enabled firms are:"
    di "  1. Reducing physical geographic expansion"
    di "  2. NOT compensating with proportional remote hiring"
    di "  3. Likely concentrating more in legacy office locations"
}
else if `b1' < 0 & `b2' > abs(`b1')*0.8 {
    di "Remote work SUBSTITUTES for geographic expansion."
    di "The decline in new MSA hiring is offset by increased remote hiring."
}
else {
    di "Results show a complex pattern requiring further investigation."
}

di _n _dup(70) "="
di "ANALYSIS COMPLETE"
di _dup(70) "="

exit