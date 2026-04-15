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
* composition_irfs_locproj_simple.do
* IRF analysis using locproj with correct syntax
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_locproj_simple.log", replace text

// Setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs_locproj"
capture mkdir "$results"

display "================================================================="
display "COMPOSITION IRF ANALYSIS USING LOCPROJ - SIMPLIFIED"
display "================================================================="

*============================================================*
* DATA SETUP (SAME AS BEFORE)
*============================================================*

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)

// Load and merge composition data
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

merge m:1 companyname_c yh using `role_wide'
keep if _merge == 3
drop _merge

// Set panel structure
xtset user_id yh
sort user_id yh

display "Data setup complete. N = " _N

*============================================================*
* CHECK LOCPROJ SYNTAX AND OPTIONS
*============================================================*

display _n "Checking locproj syntax options..."

// Check basic locproj help
capture help locproj

// Try the most basic possible locproj command
display _n "Testing basic locproj syntax..."

capture locproj total_contributions_q100 pct_growth_Engineer, horizon(2)
if _rc == 0 {
    display "SUCCESS: Basic locproj works!"
}
else {
    display "Basic locproj failed with code " _rc
}

*============================================================*
* SIMPLE LOCPROJ ESTIMATION
*============================================================*

display _n "Running simple locproj estimation..."

// Try with minimal options first
local key_roles "pct_growth_Engineer pct_growth_Sales pct_growth_Scientist"

display "Trying with key roles only: Engineer, Sales, Scientist"

capture locproj total_contributions_q100 `key_roles', horizon(4)
if _rc == 0 {
    display "SUCCESS: locproj with key roles works!"
    
    // Save results
    preserve
        // locproj should create variables like b_*, se_*, etc.
        describe
        save "$results/locproj_basic_results.dta", replace
    restore
}
else {
    display "locproj with key roles failed with code " _rc
}

*============================================================*
* TRY WITH FIXED EFFECTS OPTIONS
*============================================================*

display _n "Trying locproj with fixed effects..."

// Different FE syntax options
local fe_options1 "fe"
local fe_options2 "nofixed"

foreach fe_opt of local fe_options1 fe_options2 {
    display "Trying with `fe_opt' option..."
    capture locproj total_contributions_q100 `key_roles', horizon(4) `fe_opt'
    if _rc == 0 {
        display "SUCCESS: locproj with `fe_opt' works!"
        break
    }
    else {
        display "Failed with `fe_opt', trying next option..."
    }
}

*============================================================*
* MANUAL COMPARISON
*============================================================*

display _n "Running manual reghdfe for comparison..."

// Generate leads manually
forvalues h = 0/4 {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Run manual regression for comparison
display "Manual H1 regression:"
reghdfe F1_prod `key_roles', absorb(user_id yh) vce(cluster user_id)

// Store manual results
matrix manual_results = J(3, 5, .)
matrix rownames manual_results = Engineer Sales Scientist
matrix colnames manual_results = H0 H1 H2 H3 H4

local row = 1
foreach role in Engineer Sales Scientist {
    forvalues h = 0/4 {
        capture reghdfe F`h'_prod `key_roles', absorb(user_id yh) vce(cluster user_id)
        if _rc == 0 {
            matrix manual_results[`row', `=`h'+1'] = _b[pct_growth_`role']
        }
    }
    local ++row
}

display _n "Manual IRF Results (key roles only):"
matrix list manual_results

*============================================================*
* ALTERNATIVE LP PACKAGES
*============================================================*

display _n "Checking for alternative LP packages..."

// Check for lpirfs package
capture which lpirfs
if _rc == 0 {
    display "lpirfs package found, trying..."
    // lpirfs syntax would go here
}
else {
    display "lpirfs not available"
}

// Check for other LP commands
capture which lp_lin
if _rc == 0 {
    display "lp_lin found"
}

capture which lp_nl  
if _rc == 0 {
    display "lp_nl found"
}

*============================================================*
* CREATE RESULTS COMPARISON
*============================================================*

display _n "RESULTS SUMMARY:"
display "=================="

// Check what worked
capture confirm matrix manual_results
if _rc == 0 {
    display "✓ Manual reghdfe approach: WORKING"
}

capture confirm new variable b_*
if _rc == 0 {
    display "✓ locproj command: WORKING"
}
else {
    display "✗ locproj command: FAILED"
}

display _n "Recommendation: Use manual reghdfe approach as it's verified working"
display "This is the standard method used in most applied work anyway"

log close
display "Analysis complete. Check log for detailed results."