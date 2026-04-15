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
* composition_irfs_all_roles.do
* Clean IRF analysis with ALL 7 roles included
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_all_roles.log", replace text

// Setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs_all7"
capture mkdir "$results"

display "================================================================="
display "ALL 7 ROLES COMPOSITION IRF ANALYSIS"
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
    
    // Display role counts
    display _n "Available roles:"
    tab role_k7
    
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
display "Merge results:"
tab _merge

keep if _merge == 3
drop _merge

display "Final merged dataset: N = " _N

*============================================================*
* PANEL SETUP AND LEAD GENERATION
*============================================================*

display _n "STEP 2: Setting up panel structure and generating leads..."

// Set panel structure
xtset user_id yh
sort user_id yh

// Generate outcome leads for IRF analysis
local max_horizon 4
forvalues h = 0/`max_horizon' {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Check final sample sizes
display _n "Sample sizes by horizon:"
forvalues h = 0/`max_horizon' {
    count if !missing(F`h'_prod, total_contributions_q100)
    display "  Horizon `h': " r(N) " observations"
}

*============================================================*
* ALL 7 ROLES IRF ESTIMATION
*============================================================*

display _n "STEP 3: All 7 roles IRF estimation..."

// ALL role growth variables
local role_vars "pct_growth_Admin pct_growth_Engineer pct_growth_Finance pct_growth_Marketing pct_growth_Operations pct_growth_Sales pct_growth_Scientist"

// Display the roles we're including
display _n "Roles included in analysis:"
foreach var of local role_vars {
    local role_name = subinstr("`var'", "pct_growth_", "", .)
    display "  - `role_name'"
}

// Setup results storage
capture postfile all7_irf_results str15 role horizon coef se tstat pval ///
    ci_lower ci_upper nobs r2 using "$results/all7_irf_estimates.dta", replace

// Joint sample size check
count if !missing(pct_growth_Admin, pct_growth_Engineer, pct_growth_Finance, ///
    pct_growth_Marketing, pct_growth_Operations, pct_growth_Sales, pct_growth_Scientist, ///
    total_contributions_q100, F`max_horizon'_prod)
local joint_sample = r(N)
display _n "Joint sample for full IRF (all 7 roles): " `joint_sample'

// Run IRF estimation with all 7 roles
forvalues h = 0/`max_horizon' {
    display _n "--- Estimating Horizon `h' (All 7 Roles) ---"
    
    // Clean specification with all 7 roles
    capture reghdfe F`h'_prod `role_vars', ///
        absorb(user_id#firm_id yh) vce(cluster user_id)
    
    if _rc == 0 {
        local N_h = e(N)
        local r2_h = e(r2)
        display "  Sample size: " `N_h'
        display "  R-squared: " %5.3f `r2_h'
        
        // Store results for each role
        foreach var of local role_vars {
            local role_name = subinstr("`var'", "pct_growth_", "", .)
            
            // Extract coefficient and statistics
            local b = _b[`var']
            local se = _se[`var']
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            local ci_lower = `b' - invttail(e(df_r), 0.025) * `se'
            local ci_upper = `b' + invttail(e(df_r), 0.025) * `se'
            
            // Store in results file
            post all7_irf_results ("`role_name'") (`h') (`b') (`se') (`t') (`pval') ///
                (`ci_lower') (`ci_upper') (`N_h') (`r2_h')
            
            // Display with significance stars
            local stars ""
            if `pval' < 0.01 local stars "***"
            else if `pval' < 0.05 local stars "**"
            else if `pval' < 0.10 local stars "*"
            
            display "    `role_name': β=" %7.4f `b' " (se=" %6.4f `se' ") `stars'"
        }
        
        // Joint F-test for all composition variables
        capture test `role_vars'
        if _rc == 0 {
            display "    Joint F-test (all 7): F=" %6.2f r(F) " p-value=" %6.4f r(p)
        }
    }
    else {
        display "  ESTIMATION FAILED for horizon `h'"
        // Store missing values
        foreach var of local role_vars {
            local role_name = subinstr("`var'", "pct_growth_", "", .)
            post all7_irf_results ("`role_name'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
        }
    }
}

postclose all7_irf_results

*============================================================*
* RESULTS PROCESSING
*============================================================*

display _n "STEP 4: Processing all 7 roles results..."

// Load results for processing
use "$results/all7_irf_estimates.dta", clear

// Create coefficient matrix
reshape wide coef se tstat pval ci_lower ci_upper nobs r2, i(role) j(horizon)

// Export to CSV
export delimited using "$results/all7_irf_results.csv", replace

// Create formatted table
preserve
    reshape long coef se tstat pval ci_lower ci_upper nobs r2, i(role) j(horizon)
    
    gen coef_string = string(coef, "%7.4f")
    gen se_string = "(" + string(se, "%6.4f") + ")"
    
    replace coef_string = coef_string + "***" if pval < 0.01 & !missing(pval)
    replace coef_string = coef_string + "**" if pval >= 0.01 & pval < 0.05 & !missing(pval)
    replace coef_string = coef_string + "*" if pval >= 0.05 & pval < 0.10 & !missing(pval)
    
    keep role horizon coef_string se_string nobs
    reshape wide coef_string se_string nobs, i(role) j(horizon)
    
    export delimited using "$results/all7_irf_table_formatted.csv", replace
restore

*============================================================*
* CREATE COMBINED GRAPH WITH ALL 7 ROLES
*============================================================*

display _n "STEP 5: Creating combined graph with all 7 roles..."

use "$results/all7_irf_estimates.dta", clear

// Define colors and markers for 7 roles
local colors "navy maroon forest_green dkorange purple red blue"
local markers "circle diamond triangle square plus x smcircle"

levelsof role, local(roles)
local plot_cmd ""
local legend_labels ""
local role_counter = 1

foreach role of local roles {
    local color : word `role_counter' of `colors'
    local marker : word `role_counter' of `markers'
    
    if `role_counter' > 1 local plot_cmd "`plot_cmd' || "
    local plot_cmd "`plot_cmd' (connected coef horizon if role=="`role'", "
    local plot_cmd "`plot_cmd' lcolor(`color') mcolor(`color') msymbol(`marker') lwidth(medthick))"
    
    local legend_labels "`legend_labels' `role_counter' \"`role'""
    local ++role_counter
}

// Create combined plot with all 7 roles
twoway `plot_cmd', ///
    yline(0, lpattern(dash) lcolor(gs8)) ///
    xlabel(0(1)4, labsize(medium)) ///
    xtitle("Horizon (6-month periods)", size(medium)) ///
    ytitle("Effect on Productivity Percentile", size(medium)) ///
    title("Productivity IRFs by Role Hiring - All 7 Roles", size(large)) ///
    subtitle("User×Firm FE identification", size(medium)) ///
    legend(label(`legend_labels') cols(4) size(small)) ///
    graphregion(color(white)) plotregion(color(white))

graph export "$results/all7_irf_combined.png", replace width(1200) height(800)
display "All 7 roles combined IRF saved: $results/all7_irf_combined.png"

*============================================================*
* SUMMARY TABLE
*============================================================*

display _n _n "================================================================="
display "ALL 7 ROLES IRF RESULTS SUMMARY"
display "================================================================="

use "$results/all7_irf_estimates.dta", clear

display _n "Role" _col(15) "H0" _col(25) "H1" _col(35) "H2" _col(45) "H3" _col(55) "H4"
display "--------------------------------------------------------------------"

levelsof role, local(roles)
foreach role of local roles {
    display "`role'" _col(15) _c
    
    forvalues h = 0/4 {
        qui sum coef if role == "`role'" & horizon == `h'
        if r(N) > 0 {
            local coef = r(mean)
            qui sum pval if role == "`role'" & horizon == `h'
            local pval = r(mean)
            
            local stars ""
            if `pval' < 0.01 local stars "***"
            else if `pval' < 0.05 local stars "**"
            else if `pval' < 0.10 local stars "*"
            
            display %7.3f `coef' "`stars'" _col(`=25+10*`h'') _c
        }
    }
    display ""
}

display ""
display "*** p<0.01, ** p<0.05, * p<0.10"

log close
display _n "All 7 roles analysis complete!"