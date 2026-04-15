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
VERIFY GEOGRAPHIC EXPANSION CALCULATION LOGIC
================================================================================
This script manually calculates the geographic expansion metrics in Stata
to verify the Python calculations are correct.
================================================================================
*/

clear all
set more off

di _n "=========================================="
di "VERIFYING GEOGRAPHIC EXPANSION LOGIC"
di "=========================================="

// ============================================================================
// STEP 1: LOAD AND PREPARE LEGACY LOCATIONS
// ============================================================================

di _n "Step 1: Loading legacy locations from Python output..."

// Load the legacy locations file created by Python
import delimited "data/processed/firm_legacy_locations_clean.csv", clear
keep if is_legacy == 1
keep firm cbsa
rename firm companyname

// Create a flag for legacy location
gen legacy = 1

// Save for merging
tempfile legacy_locations
save `legacy_locations'

di "Legacy locations loaded: " _N

// Count unique firms with legacy locations
egen tag = tag(companyname)
count if tag
di "Unique firms with legacy locations: " r(N)

// ============================================================================
// STEP 2: LOAD POST-2019 HIRING DATA
// ============================================================================

di _n "Step 2: Loading LinkedIn panel for post-2019 hires..."

// Load the LinkedIn panel (using parquet through Python intermediary)
// Since Stata can't read parquet directly, using the CSV version
import delimited "data/processed/linkedin_panel_post2019_for_verification.csv", clear stringcols(_all)

// Convert numeric fields
destring yh headcount joins, replace force

// Keep only post-2019 (yh >= 4040)
keep if yh >= 4040

// We'll use joins as proxy for hires
gen hires = joins
replace hires = 0 if missing(hires)

di "Post-2019 observations: " _N
sum yh

// ============================================================================
// STEP 3: MERGE AND FLAG NEW VS LEGACY HIRES
// ============================================================================

di _n "Step 3: Flagging hires as legacy vs new geography..."

// Standardize company names for merging
gen companyname_lower = lower(companyname)

// Merge with legacy locations
merge m:1 companyname_lower cbsa using `legacy_locations', keep(1 3) gen(legacy_merge)

// Create new geography flag
gen is_new_geography = (legacy_merge == 1)  // Not matched = new geography
replace is_new_geography = 0 if legacy_merge == 3  // Matched = legacy location

// Calculate hires by type
gen hires_new_geo = hires * is_new_geography
gen hires_legacy = hires * (1 - is_new_geography)

// ============================================================================
// STEP 4: AGGREGATE TO FIRM×TIME LEVEL
// ============================================================================

di _n "Step 4: Aggregating to firm×time level..."

preserve

// Collapse to firm×time level
collapse (sum) total_hires=hires ///
               hires_new_geo ///
               hires_legacy ///
        (count) n_locations=cbsa, ///
        by(companyname yh)

// Calculate share in new geography
gen share_new_geo = hires_new_geo / total_hires
replace share_new_geo = 0 if total_hires == 0 | missing(share_new_geo)

// Summary statistics
di _n "=== MANUAL CALCULATION RESULTS ==="
sum share_new_geo, detail
di "Mean share in new geography: " %6.4f r(mean)

// Save for comparison
tempfile manual_calc
save `manual_calc'

restore

// ============================================================================
// STEP 5: LOAD AND COMPARE WITH PYTHON OUTPUT
// ============================================================================

di _n "Step 5: Comparing with Python-generated metrics..."

preserve

// Load the Python-generated geographic expansion file
import delimited "data/processed/firm_geographic_expansion.csv", clear

// Summary of Python results
di _n "=== PYTHON CALCULATION RESULTS ==="
sum share_new_geo, detail
di "Mean share in new geography: " %6.4f r(mean)

// Merge with manual calculation
rename firm companyname
merge 1:1 companyname yh using `manual_calc', gen(compare_merge) ///
    keepusing(share_new_geo) 

// Rename for comparison
rename share_new_geo share_python
rename share_new_geo share_manual

// Compare the two calculations
gen diff = share_python - share_manual
sum diff, detail

di _n "=== COMPARISON ==="
di "Observations compared: " _N
di "Mean difference (Python - Manual): " %9.6f r(mean)
di "Max absolute difference: " %9.6f r(max)

// Check correlation
corr share_python share_manual
di "Correlation: " %6.4f r(rho)

// List any large discrepancies
count if abs(diff) > 0.01
if r(N) > 0 {
    di _n "WARNING: " r(N) " observations with >1% difference"
    list companyname yh share_python share_manual diff if abs(diff) > 0.01
}

restore

// ============================================================================
// STEP 6: VERIFY A SPECIFIC EXAMPLE
// ============================================================================

di _n "Step 6: Detailed verification for a sample firm..."

// Pick a large firm to verify
local test_firm = "microsoft"

di _n "Verifying calculations for: `test_firm'"

// Check legacy locations
use `legacy_locations', clear
count if lower(companyname) == "`test_firm'"
di "Legacy locations for `test_firm': " r(N)
list cbsa if lower(companyname) == "`test_firm'"

// Check post-2019 hires
import delimited "data/processed/linkedin_panel_post2019_for_verification.csv", clear stringcols(_all)
destring yh joins, replace force
keep if lower(companyname) == "`test_firm'" & yh == 4040  // 2020-H1

// Count by legacy vs new
merge m:1 cbsa using `legacy_locations', keep(1 3) gen(is_legacy)
gen hires = joins
replace hires = 0 if missing(hires)

egen total_hires = sum(hires)
egen new_geo_hires = sum(hires * (is_legacy == 1))
gen calc_share = new_geo_hires / total_hires

di _n "Manual calculation for `test_firm' in 2020-H1:"
di "Total hires: " total_hires[1]
di "New geography hires: " new_geo_hires[1]
di "Share new geo: " %6.4f calc_share[1]

// Compare with Python output
import delimited "data/processed/firm_geographic_expansion.csv", clear
keep if lower(firm) == "`test_firm'" & yh == 4040
di _n "Python calculation for `test_firm' in 2020-H1:"
di "Share new geo: " %6.4f share_new_geo[1]

di _n "=========================================="
di "VERIFICATION COMPLETE"
di "=========================================="

exit