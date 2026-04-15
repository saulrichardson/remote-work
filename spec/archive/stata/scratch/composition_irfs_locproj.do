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
* composition_irfs_locproj.do
* IRF analysis using dedicated locproj command
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_locproj.log", replace text

// Setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs_locproj"
capture mkdir "$results"

display "================================================================="
display "COMPOSITION IRF ANALYSIS USING LOCPROJ COMMAND"
display "================================================================="

*============================================================*
* DATA SETUP
*============================================================*

display _n "STEP 1: Loading and merging data..."

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
display "User panel loaded: N = " _N

// Load and prepare composition data
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year,half)
    gen companyname_c = lower(companyname)
    
    // Keep ALL 7 roles for analysis
    keep companyname_c yh role_k7 pct_growth_role role_share
    
    // Reshape to wide format
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share* share_*
    
    // Clean missing values (set to 0 for firms without that role)
    foreach var of varlist pct_growth_* share_* {
        replace `var' = 0 if missing(`var')
    }
    
    tempfile role_wide
    save `role_wide'
restore

// Merge with user panel
merge m:1 companyname_c yh using `role_wide'
keep if _merge == 3
drop _merge

display "Final merged dataset: N = " _N

*============================================================*
* PANEL SETUP
*============================================================*

display _n "STEP 2: Setting up panel structure..."

// Set panel structure
xtset user_id yh
sort user_id yh

// Role growth variables
local role_vars "pct_growth_Admin pct_growth_Engineer pct_growth_Finance pct_growth_Marketing pct_growth_Operations pct_growth_Sales pct_growth_Scientist"

display _n "Roles included in locproj analysis:"
foreach var of local role_vars {
    local role_name = subinstr("`var'", "pct_growth_", "", .)
    display "  - `role_name'"
}

*============================================================*
* LOCPROJ ESTIMATION
*============================================================*

display _n "STEP 3: Running locproj estimation..."

// Check sample size
count if !missing(total_contributions_q100, pct_growth_Admin, pct_growth_Engineer, ///
    pct_growth_Finance, pct_growth_Marketing, pct_growth_Operations, ///
    pct_growth_Sales, pct_growth_Scientist)
display "Joint sample size: " r(N)

// Run locproj with all 7 roles
display _n "Estimating with locproj command..."

capture locproj total_contributions_q100 `role_vars', ///
    lags(0) horizon(4) ///
    absorb(user_id#firm_id yh) ///
    cluster(user_id) ///
    prefix(locproj_) ///
    graph_prefix(irf_locproj_) ///
    graph_options(scheme(s1color) graphregion(color(white)))

if _rc != 0 {
    display "locproj failed with return code " _rc
    display "Trying alternative syntax..."
    
    // Try simpler syntax
    capture locproj total_contributions_q100 `role_vars', ///
        horizon(4) lags(0) ///
        fe(user_id#firm_id yh) ///
        vce(cluster user_id)
    
    if _rc != 0 {
        display "Alternative locproj syntax also failed with return code " _rc
        display "Checking locproj installation and options..."
        
        // Check if locproj is properly installed
        which locproj
        
        // Try most basic syntax
        display "Trying basic locproj syntax..."
        capture locproj total_contributions_q100 pct_growth_Engineer, ///
            horizon(4) lags(0)
        
        if _rc == 0 {
            display "Basic locproj works - issue is with advanced options"
        }
        else {
            display "Basic locproj also fails - installation issue"
        }
    }
    else {
        display "Alternative locproj syntax succeeded!"
    }
}
else {
    display "locproj estimation completed successfully!"
}

*============================================================*
* ALTERNATIVE: TRY LP_LIN IF AVAILABLE
*============================================================*

display _n "STEP 4: Trying lp_lin as alternative..."

// Check if lp_lin is available
capture which lp_lin
if _rc == 0 {
    display "lp_lin is available, trying..."
    
    capture lp_lin total_contributions_q100 `role_vars', ///
        lags(0) leads(4) ///
        fe_options(absorb(user_id#firm_id yh)) ///
        vce(cluster user_id)
    
    if _rc == 0 {
        display "lp_lin estimation succeeded!"
    }
    else {
        display "lp_lin failed with return code " _rc
    }
}
else {
    display "lp_lin not available"
}

*============================================================*
* ALTERNATIVE: TRY IVREG2 WITH LEADS IF LP COMMANDS FAIL
*============================================================*

display _n "STEP 5: Manual LP verification using reghdfe..."

// If dedicated LP commands fail, verify with manual approach
display "Running manual verification to ensure data setup is correct..."

// Generate leads manually for verification
forvalues h = 0/4 {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Test one horizon to verify setup
capture reghdfe F1_prod `role_vars', absorb(user_id#firm_id yh) vce(cluster user_id)
if _rc == 0 {
    display "Manual reghdfe verification successful at H1:"
    display "  N = " e(N)
    display "  R-squared = " %5.3f e(r2)
    
    // Show a few key coefficients
    local b_eng = _b[pct_growth_Engineer]
    local b_sales = _b[pct_growth_Sales]
    display "  Engineer coef = " %6.3f `b_eng'
    display "  Sales coef = " %6.3f `b_sales'
}
else {
    display "Manual reghdfe verification failed - data issue"
}

*============================================================*
* RESULTS EXPORT AND COMPARISON
*============================================================*

display _n "STEP 6: Results export and comparison..."

// If locproj worked, export results
capture confirm new variable locproj_b_*
if _rc == 0 {
    display "locproj results found - exporting..."
    
    // Export locproj results
    preserve
        keep locproj_b_* locproj_se_* locproj_t_* locproj_p_*
        keep if _n == 1
        export delimited using "$results/locproj_results.csv", replace
    restore
    
    display "locproj results exported to: $results/locproj_results.csv"
}
else {
    display "No locproj results found"
}

// If lp_lin worked, export those results
capture confirm new variable b_*
if _rc == 0 {
    display "lp_lin results found - exporting..."
    // Export lp_lin results if available
}

*============================================================*
* CREATE GRAPHS FROM LOCPROJ RESULTS
*============================================================*

display _n "STEP 7: Creating graphs from locproj results..."

// If locproj created graph data, use it
capture confirm new variable locproj_b_*
if _rc == 0 {
    display "Creating IRF graphs from locproj output..."
    
    // Create individual graphs for each role
    foreach role in Admin Engineer Finance Marketing Operations Sales Scientist {
        capture {
            preserve
                // Create horizon variable
                gen horizon = _n - 1 if _n <= 5
                keep if !missing(horizon)
                
                // Extract coefficients and standard errors for this role
                gen coef = .
                gen se = .
                
                forvalues h = 0/4 {
                    replace coef = locproj_b_pct_growth_`role'_`h' if horizon == `h'
                    replace se = locproj_se_pct_growth_`role'_`h' if horizon == `h'
                }
                
                // Create confidence intervals
                gen ci_lower = coef - 1.96 * se
                gen ci_upper = coef + 1.96 * se
                
                // Create graph
                twoway (rcap ci_lower ci_upper horizon, lcolor(gs10)) ///
                       (connected coef horizon, lcolor(navy) mcolor(navy) ///
                        msymbol(circle) lwidth(thick)), ///
                       yline(0, lpattern(dash) lcolor(gs8)) ///
                       xlabel(0(1)4) ///
                       xtitle("Horizon") ///
                       ytitle("Effect on Productivity") ///
                       title("locproj IRF: `role'") ///
                       legend(off) ///
                       graphregion(color(white)) plotregion(color(white))
                
                graph export "$results/locproj_irf_`role'.png", replace
            restore
        }
    }
}

*============================================================*
* SUMMARY AND DIAGNOSTICS
*============================================================*

display _n _n "================================================================="
display "LOCPROJ ANALYSIS SUMMARY"
display "================================================================="

display _n "Command attempts:"
display "1. locproj with user#firm FE and clustering"
display "2. Alternative locproj syntax"  
display "3. lp_lin (if available)"
display "4. Manual reghdfe verification"

display _n "Data setup:"
display "- Sample size: " _N " total observations"
display "- Panel structure: user_id × yh"
display "- 7 role composition variables included"

display _n "Files potentially created in $results/:"
display "- locproj_results.csv (if locproj succeeded)"
display "- locproj_irf_[Role].png (individual IRF graphs)"

// Show which method worked
capture confirm new variable locproj_b_*
if _rc == 0 {
    display _n "SUCCESS: locproj estimation completed"
}
else {
    display _n "NOTE: locproj may have failed - check log for errors"
    display "Consider using manual reghdfe approach as verified working method"
}

log close

display _n "locproj analysis log saved to: composition_irfs_locproj.log"
display "================================================================="