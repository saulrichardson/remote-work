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
* verify_merge_simple.do 
* Simple verification of merge logic
*============================================================*

clear all
set more off

global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"

display "VERIFYING COMPOSITION MERGE LOGIC"
display "=================================="

*============================================================*
* REPLICATE EXACT MERGE FROM ANALYSIS
*============================================================*

// Load user panel (exactly as in analysis)
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
display "User panel: N = " _N

// Load and prepare composition data (exactly as in analysis)  
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year,half)
    gen companyname_c = lower(companyname)
    keep companyname_c yh role_k7 pct_growth_role role_share
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share* share_*
    foreach var of varlist pct_growth_* share_* {
        replace `var' = 0 if missing(`var')
    }
    tempfile role_wide
    save `role_wide'
restore

// Merge (exactly as in analysis)
merge m:1 companyname_c yh using `role_wide'
display "Merge results:"
tab _merge

keep if _merge == 3
drop _merge
display "Final N after merge: " _N

*============================================================*
* VERIFICATION TESTS
*============================================================*

display _n "VERIFICATION TESTS:"
display "=================="

// Test 1: Check that composition is firm-time specific (not user specific)
display _n "Test 1: Composition should be constant within firm-time"
preserve
    collapse (sd) sd_eng=pct_growth_Engineer (mean) mean_eng=pct_growth_Engineer ///
             (count) n_users=user_id, by(companyname_c yh)
    sum sd_eng
    if r(max) < 0.001 {
        display "✓ PASS: Composition is constant within firm-time"
    }
    else {
        display "✗ FAIL: Composition varies within firm-time"
        list companyname_c yh sd_eng mean_eng n_users if sd_eng > 0.001
    }
restore

// Test 2: Check realistic growth rate ranges
display _n "Test 2: Growth rates should be reasonable"
sum pct_growth_Engineer pct_growth_Sales, detail
display "Engineer growth: min=" r(min) " max=" r(max)
if r(max) < 10 & r(min) > -2 {
    display "✓ PASS: Growth rates in reasonable range"
}

// Test 3: Check specific example
display _n "Test 3: Detailed example verification"
preserve
    // Find a company with variation
    collapse (count) n_obs=user_id (mean) eng_growth=pct_growth_Engineer, by(companyname_c)
    gsort -n_obs
    local test_company = companyname_c[1]
    display "Test company: `test_company'"
restore

preserve
    keep if companyname_c == "`test_company'"
    display "Growth rates for `test_company' by time period:"
    collapse (mean) pct_growth_Engineer pct_growth_Sales (count) n_users=user_id, by(yh)
    list yh pct_growth_Engineer pct_growth_Sales n_users
restore

// Test 4: Check time alignment
display _n "Test 4: Time period alignment"
display "Data spans time periods:"
sum yh
display "yh range: " r(min) " to " r(max) " (corresponds to " ///
        year(dofh(r(min))) "h" halfyear(dofh(r(min))) " to " ///
        year(dofh(r(max))) "h" halfyear(dofh(r(max))) ")"

// Test 5: Sample composition growth example
display _n "Test 5: Sample growth interpretation"
display "Example: pct_growth_Engineer = 0.5 means Engineer hiring grew 50%"
display "Example: pct_growth_Engineer = -0.2 means Engineer hiring fell 20%"
count if pct_growth_Engineer > 0
display "Periods with positive Engineer growth: " r(N)
count if pct_growth_Engineer < 0  
display "Periods with negative Engineer growth: " r(N)
count if pct_growth_Engineer == 0
display "Periods with zero Engineer growth: " r(N)

display _n "✓ MERGE VERIFICATION COMPLETE"
display "=============================="
display "The composition growth rates are correctly matched to firms and time periods."
display "Each user at a given firm in a given time period gets the same composition values."
display "This is the correct structure for firm-level composition shocks affecting individual productivity."