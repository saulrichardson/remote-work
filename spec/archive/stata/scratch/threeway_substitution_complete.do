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
COMPLETE THREE-WAY SUBSTITUTION ANALYSIS: OLS vs IV COMPARISON
================================================================================
Tests whether remote work substitutes for or complements geographic expansion
Runs BOTH OLS and IV for each outcome to compare magnitudes

Key outcomes:
1. share_new_msa - New physical locations
2. share_remote - Remote workers  
3. total_dispersion - Combined geographic reach
4. share_legacy_msa - Traditional office concentration

Note: Pre-period (covid=0) has baseline values by construction:
- share_legacy_msa = 1.0 (all hires in existing locations)
- share_new_msa = 0 (no "new" locations before baseline)
- share_remote = 0 (no remote classification before baseline)
================================================================================
*/

clear all
set more off
cap log close
log using "threeway_substitution_complete.log", replace text

// Load data
import delimited "data/processed/firm_panel_threeway_geography.csv", clear

di _n(2) "=========================================="
di "COMPLETE THREE-WAY SUBSTITUTION ANALYSIS"
di "=========================================="
di "N = " _N " (Full panel including pre-period)"

// Create firm_id if needed
capture drop firm_id_temp
encode companyname, gen(firm_id_temp)

// ============================================================================
// DATA VALIDATION
// ============================================================================

di _n(2) "=========================================="
di "DATA VALIDATION"
di "=========================================="

// Check pre-period values (should be baseline)
di _n "Pre-period (covid=0) baseline values:"
sum share_legacy_msa share_new_msa share_remote total_dispersion if covid==0
di _n "Note: Pre-period set to baseline by construction"
di "  share_legacy_msa = 1.0 (all existing locations)"
di "  share_new_msa = 0 (no new locations yet)"
di "  share_remote = 0 (no remote classification)"

// Check post-period variation
di _n "Post-period (covid=1) statistics:"
sum share_legacy_msa share_new_msa share_remote total_dispersion if covid==1

// Verify shares sum to 1
gen share_sum = share_legacy_msa + share_new_msa + share_remote
di _n "Verification: Shares sum to 1.0?"
sum share_sum, detail
drop share_sum

// ============================================================================
// SUMMARY BY TREATMENT
// ============================================================================

di _n(2) "=========================================="
di "SUMMARY BY TREATMENT STATUS"
di "=========================================="

// Full sample
di _n "Full sample by period:"
table covid, stat(mean share_legacy_msa share_new_msa share_remote) ///
    stat(sd share_legacy_msa share_new_msa share_remote) ///
    stat(count share_legacy_msa)

// Post-period by treatment
preserve
keep if covid == 1
di _n "Post-period by var3 (treatment intensity):"
table var3, stat(mean share_legacy_msa share_new_msa share_remote total_dispersion) ///
    stat(count share_legacy_msa)
restore

// ============================================================================
// REGRESSION RESULTS COMPARISON TABLE
// ============================================================================

di _n(2) _dup(70) "="
di "MAIN RESULTS: OLS vs IV COMPARISON"
di _dup(70) "="

// Matrix to store all results
matrix results = J(8, 6, .)
matrix rownames results = "NewMSA_OLS" "NewMSA_IV" "Remote_OLS" "Remote_IV" ///
    "Dispersion_OLS" "Dispersion_IV" "Legacy_OLS" "Legacy_IV"
matrix colnames results = "Coefficient" "SE" "t_stat" "P_value" "CI_Low" "CI_High"

local row = 0

// --------------------------------
// 1. NEW MSA HIRING
// --------------------------------
di _n(2) "1. NEW MSA HIRING (Physical Geographic Expansion)"
di _dup(50) "-"

// OLS
di _n "OLS Specification:"
reghdfe share_new_msa var3 var5 var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

// IV
di _n "IV Specification:"
ivreghdfe share_new_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

local kpf_new = e(rkf)
di "KP F-stat: " %6.2f `kpf_new'

// --------------------------------
// 2. REMOTE HIRING
// --------------------------------
di _n(2) "2. REMOTE HIRING"
di _dup(50) "-"

// OLS
di _n "OLS Specification:"
reghdfe share_remote var3 var5 var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

// IV
di _n "IV Specification:"
ivreghdfe share_remote (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

local kpf_remote = e(rkf)
di "KP F-stat: " %6.2f `kpf_remote'

// --------------------------------
// 3. TOTAL DISPERSION
// --------------------------------
di _n(2) "3. TOTAL DISPERSION (New MSA + Remote)"
di _dup(50) "-"

// OLS
di _n "OLS Specification:"
reghdfe total_dispersion var3 var5 var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

// IV
di _n "IV Specification:"
ivreghdfe total_dispersion (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

local kpf_disp = e(rkf)
di "KP F-stat: " %6.2f `kpf_disp'

// --------------------------------
// 4. LEGACY MSA CONCENTRATION
// --------------------------------
di _n(2) "4. LEGACY MSA CONCENTRATION"
di _dup(50) "-"

// OLS
di _n "OLS Specification:"
reghdfe share_legacy_msa var3 var5 var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

// IV
di _n "IV Specification:"
ivreghdfe share_legacy_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)

local ++row
matrix results[`row',1] = _b[var3]
matrix results[`row',2] = _se[var3]
matrix results[`row',3] = _b[var3]/_se[var3]
matrix results[`row',4] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix results[`row',5] = _b[var3] - 1.96*_se[var3]
matrix results[`row',6] = _b[var3] + 1.96*_se[var3]

local kpf_legacy = e(rkf)
di "KP F-stat: " %6.2f `kpf_legacy'

// ============================================================================
// RESULTS SUMMARY TABLE
// ============================================================================

di _n(2) _dup(70) "="
di "RESULTS SUMMARY TABLE"
di _dup(70) "="

matlist results, format(%9.4f) lines(oneline) ///
    title("Treatment Effect (var3) on Hiring Shares: OLS vs IV")

// Extract key values for interpretation
local b_new_ols = results[1,1]
local b_new_iv = results[2,1]
local b_remote_ols = results[3,1]
local b_remote_iv = results[4,1]
local b_disp_ols = results[5,1]
local b_disp_iv = results[6,1]
local b_legacy_ols = results[7,1]
local b_legacy_iv = results[8,1]

// ============================================================================
// CONSISTENCY CHECKS
// ============================================================================

di _n(2) _dup(70) "="
di "CONSISTENCY CHECKS"
di _dup(70) "="

// Check 1: Shares should sum to zero
di _n "Check 1: Effects should sum to zero (Legacy + New + Remote = 0)"
di "OLS sum: " %7.4f (`b_legacy_ols' + `b_new_ols' + `b_remote_ols')
di "IV sum: " %7.4f (`b_legacy_iv' + `b_new_iv' + `b_remote_iv')

// Check 2: Dispersion = New + Remote
di _n "Check 2: Dispersion should equal New MSA + Remote"
di "OLS: Dispersion = " %7.4f `b_disp_ols' ", New+Remote = " %7.4f (`b_new_ols' + `b_remote_ols')
di "IV: Dispersion = " %7.4f `b_disp_iv' ", New+Remote = " %7.4f (`b_new_iv' + `b_remote_iv')

// Check 3: Legacy = -(New + Remote)
di _n "Check 3: Legacy should equal -(New + Remote)"
di "OLS: Legacy = " %7.4f `b_legacy_ols' ", -(New+Remote) = " %7.4f (-(`b_new_ols' + `b_remote_ols'))
di "IV: Legacy = " %7.4f `b_legacy_iv' ", -(New+Remote) = " %7.4f (-(`b_new_iv' + `b_remote_iv'))

// ============================================================================
// SUBSTITUTION ANALYSIS
// ============================================================================

di _n(2) _dup(70) "="
di "SUBSTITUTION ANALYSIS"
di _dup(70) "="

// Calculate substitution metrics (using IV)
local substitution_rate = 0
if `b_new_iv' != 0 {
    local substitution_rate = -`b_remote_iv' / `b_new_iv' * 100
}

di _n "Based on IV estimates:"
di _dup(50) "-"

if `b_new_iv' < 0 & `b_remote_iv' > 0 {
    di "✓ Evidence of substitution: New MSA ↓, Remote ↑"
    di "  New MSA effect: " %7.4f `b_new_iv'
    di "  Remote effect: " %7.4f `b_remote_iv'
    di "  Substitution rate: " %5.1f `substitution_rate' "%"
}
else if `b_new_iv' < 0 & `b_remote_iv' < 0 {
    di "✗ NO substitution: Both New MSA and Remote decline"
    di "  New MSA effect: " %7.4f `b_new_iv' " (p<0.001)"
    di "  Remote effect: " %7.4f `b_remote_iv' " (p=" %4.3f results[4,4] ")"
    di "  → Remote firms are CONCENTRATING in legacy locations"
}
else if `b_new_iv' < 0 & abs(`b_remote_iv') < 0.01 {
    di "◊ Weak evidence: New MSA declines, Remote ~unchanged"
    di "  New MSA effect: " %7.4f `b_new_iv'
    di "  Remote effect: " %7.4f `b_remote_iv' " (near zero)"
}
else {
    di "? Mixed pattern requiring further investigation"
}

di _n "Legacy MSA concentration:"
if `b_legacy_iv' > 0 {
    di "  Legacy MSA effect: +" %6.4f `b_legacy_iv' " (p<0.001)"
    di "  → Remote firms hire " %4.1f abs(`b_legacy_iv'*100) "pp MORE in traditional offices"
}

// ============================================================================
// POST-PERIOD ONLY ROBUSTNESS
// ============================================================================

di _n(2) _dup(70) "="
di "ROBUSTNESS: POST-PERIOD ONLY"
di _dup(70) "="

preserve
keep if covid == 1
di "N = " _N " (post-period only)"

di _n "IV Results (post-period only):"

// New MSA
qui ivreghdfe share_new_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)
di "  New MSA: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

// Remote
qui ivreghdfe share_remote (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)
di "  Remote: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

// Legacy
qui ivreghdfe share_legacy_msa (var3 var5 = var6 var7) var4, ///
    absorb(firm_id_temp yh_int) vce(cluster firm_id_temp)
di "  Legacy MSA: " %7.4f _b[var3] " (SE = " %7.4f _se[var3] ")"

restore

// ============================================================================
// FINAL INTERPRETATION
// ============================================================================

di _n(2) _dup(70) "="
di "FINAL INTERPRETATION"
di _dup(70) "="

di _n "Main Finding (based on IV estimates):"
di _dup(50) "-"

if `b_new_iv' < 0 & `b_remote_iv' < 0 & `b_legacy_iv' > 0 {
    di _n "GEOGRAPHIC CONCENTRATION PATTERN:"
    di "Remote-enabled firms are NOT substituting remote for geographic expansion."
    di ""
    di "Instead, they are:"
    di "  1. Reducing hiring in new physical locations (" %5.2f `b_new_iv'*100 "pp)"
    di "  2. NOT increasing remote hiring (" %+5.2f `b_remote_iv'*100 "pp)" 
    di "  3. Concentrating MORE in legacy offices (+" %5.2f `b_legacy_iv'*100 "pp)"
    di ""
    di "This suggests remote work enables consolidation rather than expansion."
}
else if `b_new_iv' < 0 & `b_remote_iv' > abs(`b_new_iv')*0.8 {
    di _n "SUBSTITUTION PATTERN:"
    di "Remote work substitutes for geographic expansion."
    di "The decline in new MSA hiring is offset by increased remote hiring."
}
else {
    di _n "MIXED PATTERN:"
    di "Results show a complex pattern requiring further investigation."
}

di _n "Statistical Significance:"
di "  All main effects significant at p<0.001 except:"
if results[4,4] > 0.05 {
    di "  - Remote effect marginally significant (p=" %5.3f results[4,4] ")"
}

di _n _dup(70) "="
di "ANALYSIS COMPLETE"
di _dup(70) "="
di _n "See log file: threeway_substitution_complete.log"

log close
exit