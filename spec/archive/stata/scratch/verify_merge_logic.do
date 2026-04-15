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

*============================================================*
* verify_merge_logic.do
* Verify that composition growth rates are correctly merged
*============================================================*

clear all
set more off
capture log close
log using "verify_merge_logic.log", replace text

global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"

display "================================================================="
display "VERIFYING MERGE LOGIC FOR COMPOSITION DATA"
display "================================================================="

*============================================================*
* STEP 1: EXAMINE COMPOSITION DATA STRUCTURE
*============================================================*

display _n "STEP 1: Examining composition data structure..."

// Load composition data to understand structure
import delimited "$processed_data/role_k7_scaling_growth.csv", clear

display "Original composition data:"
display "N = " _N
describe companyname year half role_k7 pct_growth_role

// Check the time variable creation
gen yh = yh(year,half)
display _n "Time variable verification:"
display "year=2019, half=1 -> yh=" yh(2019,1)
display "year=2019, half=2 -> yh=" yh(2019,2)

// Show sample of the data structure
display _n "Sample of composition data (first 10 obs):"
list companyname year half yh role_k7 pct_growth_role in 1/10

// Check for potential issues
display _n "Checking for missing or problematic values:"
count if missing(companyname)
display "Missing company names: " r(N)
count if missing(pct_growth_role)  
display "Missing growth rates: " r(N)
count if pct_growth_role == .
display "Growth rates coded as .: " r(N)

// Check role distribution
display _n "Role distribution in composition data:"
tab role_k7

*============================================================*
* STEP 2: VERIFY RESHAPE LOGIC
*============================================================*

display _n "STEP 2: Verifying reshape logic..."

// Create clean merge key
gen companyname_c = lower(companyname)

// Keep essential variables for merge verification
keep companyname_c yh role_k7 pct_growth_role

// Show pre-reshape sample
display _n "Before reshape - sample observations:"
display "Company: " companyname_c[1] ", Time: " yh[1] ", Role: " role_k7[1] ", Growth: " pct_growth_role[1]
display "Company: " companyname_c[2] ", Time: " yh[2] ", Role: " role_k7[2] ", Growth: " pct_growth_role[2]

// Reshape to wide
reshape wide pct_growth_role, i(companyname_c yh) j(role_k7) string
rename pct_growth_role* pct_growth_*

display _n "After reshape:"
display "Variables created:"
describe pct_growth_*

// Show sample of reshaped data
display _n "Sample of reshaped data:"
list companyname_c yh pct_growth_Engineer pct_growth_Sales in 1/5

*============================================================*
* STEP 3: VERIFY USER PANEL STRUCTURE
*============================================================*

display _n "STEP 3: Examining user panel structure..."

// Save reshaped composition data temporarily
tempfile comp_wide
save `comp_wide'

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear

display "User panel structure:"
display "N = " _N
describe user_id firm_id companyname yh total_contributions_q100

// Check time variable in user panel
display _n "User panel time variable sample:"
list user_id companyname yh total_contributions_q100 in 1/5

// Create merge key for user panel
gen companyname_c = lower(companyname)

*============================================================*
* STEP 4: TEST MERGE LOGIC
*============================================================*

display _n "STEP 4: Testing merge logic..."

// Perform merge
merge m:1 companyname_c yh using `comp_wide'

display "Merge results:"
tab _merge

// Show examples of successful merges
display _n "Examples of successful merges (_merge=3):"
list user_id companyname_c yh pct_growth_Engineer pct_growth_Sales total_contributions_q100 if _merge==3 in 1/10

// Check for logical consistency
display _n "Verifying logical consistency..."

// For a specific company-time, all users should have same composition growth
preserve
    keep if _merge == 3
    collapse (mean) pct_growth_Engineer pct_growth_Sales (count) n_users=user_id, by(companyname_c yh)
    
    display "Sample: composition should be constant within firm-time:"
    list companyname_c yh pct_growth_Engineer pct_growth_Sales n_users in 1/10
restore

*============================================================*
* STEP 5: VERIFY SPECIFIC EXAMPLES
*============================================================*

display _n "STEP 5: Detailed verification for specific examples..."

keep if _merge == 3

// Pick a company and show the logic
display _n "Detailed example - finding a company with variation:"
preserve
    // Find a company with multiple time periods and multiple users
    collapse (count) n_obs=user_id, by(companyname_c)
    sort n_obs
    local example_company = companyname_c[_N-5]  // Pick a company with decent size
    display "Example company: " "`example_company'"
restore

preserve
    keep if companyname_c == "`example_company'"
    sort yh user_id
    
    display "For company `example_company':"
    display "Time periods available:"
    tab yh
    
    display "Sample of users and their composition exposure:"
    list user_id yh pct_growth_Engineer pct_growth_Sales total_contributions_q100 in 1/15
    
    // Check that composition is constant within firm-time
    display "Verifying composition is constant within firm-time:"
    collapse (mean) pct_growth_Engineer (sd) sd_eng=pct_growth_Engineer ///
             (mean) pct_growth_Sales (sd) sd_sales=pct_growth_Sales ///
             (count) n_users=user_id, by(yh)
    
    list yh pct_growth_Engineer sd_eng pct_growth_Sales sd_sales n_users
    
    // Standard deviations should be 0 (or very close) within firm-time
    sum sd_eng sd_sales
    if r(max) > 0.001 {
        display "WARNING: Composition varies within firm-time periods!"
    }
    else {
        display "✓ VERIFIED: Composition is constant within firm-time as expected"
    }
restore

*============================================================*
* STEP 6: VERIFY TEMPORAL ALIGNMENT
*============================================================*

display _n "STEP 6: Verifying temporal alignment..."

// Check that we're matching the right time periods
display "Time period alignment check:"
display "User panel time range:"
sum yh
local user_min = r(min)
local user_max = r(max)
display "User panel: yh from " `user_min' " to " `user_max'

// Load composition data again to check time range
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year,half)
    sum yh
    local comp_min = r(min)
    local comp_max = r(max)
    display "Composition data: yh from " `comp_min' " to " `comp_max'
    
    // Check overlap
    local overlap_start = max(`user_min', `comp_min')
    local overlap_end = min(`user_max', `comp_max')
    display "Overlap period: yh from " `overlap_start' " to " `overlap_end'
restore

*============================================================*
* FINAL VERIFICATION
*============================================================*

display _n "FINAL VERIFICATION SUMMARY:"
display "=========================="

// Count final merged observations
count
display "Total merged observations: " r(N)

// Check for any obvious data issues
count if missing(pct_growth_Engineer, pct_growth_Sales)
display "Observations missing key composition variables: " r(N)

count if pct_growth_Engineer == 0 & pct_growth_Sales == 0 ///
      & pct_growth_Marketing == 0 & pct_growth_Finance == 0 ///
      & pct_growth_Operations == 0 & pct_growth_Admin == 0 ///
      & pct_growth_Scientist == 0
display "Observations with all composition growth = 0: " r(N)

// This is expected for firms with no hiring in that period
display "(Zero growth is expected for firms with no hiring)"

display _n "✓ MERGE LOGIC VERIFICATION COMPLETE"

log close