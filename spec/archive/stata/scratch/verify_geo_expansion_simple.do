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
VERIFY GEOGRAPHIC EXPANSION CALCULATION - SIMPLE APPROACH
================================================================================
Verify that the share_new_geo values in our merged dataset make sense
================================================================================
*/

clear all
set more off

di _n "=========================================="
di "VERIFYING GEOGRAPHIC EXPANSION CALCULATIONS"
di "=========================================="

// ============================================================================
// STEP 1: LOAD THE MERGED DATASET
// ============================================================================

import delimited "data/processed/firm_panel_full_with_geography.csv", clear

di "Total observations: " _N

// ============================================================================
// STEP 2: CHECK PRE VS POST PERIOD VALUES
// ============================================================================

di _n "=== CHECKING PRE/POST PERIOD LOGIC ==="

// Pre-period should all be 0
sum share_new_geo if covid == 0
local pre_mean = r(mean)
local pre_sd = r(sd)
di "Pre-period (covid=0): mean = " %6.4f `pre_mean' ", sd = " %6.4f `pre_sd'

if `pre_mean' != 0 | `pre_sd' != 0 {
    di "ERROR: Pre-period should have share_new_geo = 0!"
}
else {
    di "✓ Pre-period correctly set to 0"
}

// Post-period should have variation
sum share_new_geo if covid == 1
di "Post-period (covid=1): mean = " %6.4f r(mean) ", sd = " %6.4f r(sd)

// ============================================================================
// STEP 3: VERIFY SHARE BOUNDS
// ============================================================================

di _n "=== VERIFYING SHARE BOUNDS ==="

// Check if all values are between 0 and 1
count if share_new_geo < 0 | share_new_geo > 1
if r(N) > 0 {
    di "ERROR: " r(N) " observations outside [0,1] bounds"
    list companyname yh share_new_geo if share_new_geo < 0 | share_new_geo > 1
}
else {
    di "✓ All share values within [0,1] bounds"
}

// ============================================================================
// STEP 4: CHECK RELATIONSHIP WITH HIRE COUNTS
// ============================================================================

di _n "=== CHECKING HIRE COUNT LOGIC ==="

// In post-period, firms with no hires should have share = 0
count if covid == 1 & total_hires == 0 & share_new_geo != 0
if r(N) > 0 {
    di "WARNING: " r(N) " post-period obs with zero hires but non-zero share"
}

// Check that new_geo_hires <= total_hires
gen ratio_check = new_geo_hires / total_hires if total_hires > 0
count if ratio_check > 1.001  // Allow small rounding error
if r(N) > 0 {
    di "ERROR: " r(N) " observations where new_geo_hires > total_hires"
}

// Verify the calculation: share = new_geo_hires / total_hires
gen calc_share = new_geo_hires / total_hires if total_hires > 0
replace calc_share = 0 if total_hires == 0 | missing(calc_share)

gen diff = abs(share_new_geo - calc_share)
sum diff if covid == 1, detail

if r(max) > 0.001 {
    di "WARNING: Maximum difference between stored and calculated share: " %9.6f r(max)
    list companyname yh share_new_geo calc_share diff if diff > 0.001 & covid == 1
}
else {
    di "✓ Share calculation verified: share = new_geo_hires / total_hires"
}

// ============================================================================
// STEP 5: CHECK SPECIFIC EXAMPLES
// ============================================================================

di _n "=== CHECKING SPECIFIC EXAMPLES ==="

// Look at firms with highest geographic expansion
preserve
keep if covid == 1 & total_hires > 100  // Focus on firms with substantial hiring
gsort -share_new_geo
di _n "Top 10 firms by geographic expansion (>100 hires):"
list companyname yh total_hires new_geo_hires share_new_geo n_new_locations in 1/10

restore

// Look at firms with zero geographic expansion
preserve
keep if covid == 1 & share_new_geo == 0 & total_hires > 100
di _n "Examples of firms with zero expansion despite hiring:"
list companyname yh total_hires in 1/5

restore

// ============================================================================
// STEP 6: AGGREGATE STATISTICS
// ============================================================================

di _n "=== AGGREGATE STATISTICS ==="

// By year-half
preserve
keep if covid == 1
gen year = int(yh_int/2)

collapse (mean) mean_share=share_new_geo ///
         (sum) total_new=new_geo_hires total_all=total_hires ///
         (count) n_firms=share_new_geo, by(year)

gen aggregate_share = total_new / total_all

di _n "Geographic expansion by year:"
list year mean_share aggregate_share n_firms

restore

// ============================================================================
// STEP 7: COMPARE WITH RAW GEOGRAPHIC EXPANSION FILE
// ============================================================================

di _n "=== COMPARING WITH SOURCE FILE ==="

preserve

// Load the original geographic expansion file
import delimited "data/processed/firm_geographic_expansion.csv", clear
rename firm companyname_temp
gen companyname = lower(companyname_temp)
drop companyname_temp

tempfile geo_original
save `geo_original'

// Load merged file
import delimited "data/processed/firm_panel_full_with_geography.csv", clear
keep if covid == 1
gen companyname_lower = lower(companyname)

// Merge
merge 1:1 companyname_lower yh using `geo_original', ///
    keepusing(share_new_geo) gen(check_merge)

// Compare values
rename share_new_geo share_merged
rename share_new_geo share_original

gen value_diff = abs(share_merged - share_original)
sum value_diff, detail

count if check_merge == 3  // Both files
local n_matched = r(N)
count if check_merge == 3 & value_diff < 0.0001
local n_exact = r(N)

di _n "Comparison results:"
di "Matched observations: " `n_matched'
di "Exact matches (diff < 0.0001): " `n_exact'
di "Match rate: " %6.2f (`n_exact'/`n_matched')*100 "%"

if `n_exact' < `n_matched' {
    di _n "Mismatched examples:"
    list companyname yh share_merged share_original value_diff ///
        if check_merge == 3 & value_diff >= 0.0001
}

restore

// ============================================================================
// FINAL SUMMARY
// ============================================================================

di _n "=========================================="
di "VERIFICATION SUMMARY"
di "=========================================="

qui sum share_new_geo if covid == 1
di "Post-period mean share_new_geo: " %6.4f r(mean)
di "Post-period N: " r(N)

qui sum share_new_geo if covid == 1 & var3 == 0
local mean_control = r(mean)
qui sum share_new_geo if covid == 1 & var3 == 1
local mean_treated = r(mean)

di _n "By treatment status (post-period):"
di "Control (var3=0): " %6.4f `mean_control'
di "Treated (var3=1): " %6.4f `mean_treated'
di "Raw difference: " %6.4f (`mean_treated' - `mean_control')

di _n "=========================================="
di "VERIFICATION COMPLETE"
di "=========================================="

exit