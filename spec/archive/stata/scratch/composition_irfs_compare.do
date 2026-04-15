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
* composition_irfs_compare.do
* Compare single-variable vs multi-variable IRF approaches
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_compare.log", replace text

global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_test"
capture mkdir "$results"

display "============================================================"
display "COMPOSITION IRF COMPARISON: SINGLE vs MULTI-VARIABLE"
display "============================================================"

*============================================================*
* SETUP: Load and merge data (using fixed time variables)
*============================================================*

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
    
    // Keep key roles
    keep if inlist(role_k7, "Engineer", "Sales", "Marketing", "Finance", "Operations")
    keep companyname_c yh role_k7 pct_growth_role role_share
    
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share* share_*
    
    tempfile role_wide
    save `role_wide'
restore

// Merge
merge m:1 companyname_c yh using `role_wide'
keep if _merge == 3
drop _merge

display "Final merged dataset: N = " _N

// Setup panel and generate leads
xtset user_id yh
sort user_id yh
forvalues h = 0/4 {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Check final sample
count if !missing(F4_prod, total_contributions_q100)
display "IRF analysis sample: " r(N)

*============================================================*
* APPROACH 1: Individual Role Analysis (Single Variable)
*============================================================*

display _n "================================================================="
display "APPROACH 1: INDIVIDUAL ROLE ANALYSIS"
display "================================================================="

// Setup results file for individual analysis
capture postfile single_results str15 role horizon coef se pval nobs ///
    using "$results/single_variable_irfs.dta", replace

// Test each role individually
local roles "Engineer Sales Marketing Finance Operations"
foreach role of local roles {
    
    capture confirm variable pct_growth_`role'
    if _rc == 0 {
        count if !missing(pct_growth_`role', total_contributions_q100, F4_prod)
        local n_role = r(N)
        
        display _n "========== `role' Analysis (N = `n_role') =========="
        
        if `n_role' > 1000 {
            // Basic stats
            qui sum pct_growth_`role', detail
            display "Growth stats: Mean=" %6.3f r(mean) " SD=" %6.3f r(sd) " P90=" %6.3f r(p90)
            
            // Run IRF
            forvalues h = 0/4 {
                capture reghdfe F`h'_prod pct_growth_`role' var4, ///
                    absorb(user_id firm_id yh) vce(cluster user_id)
                
                if _rc == 0 {
                    local b = _b[pct_growth_`role']
                    local se = _se[pct_growth_`role']
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    local N = e(N)
                    
                    // Store results
                    post single_results ("`role'") (`h') (`b') (`se') (`pval') (`N')
                    
                    // Display with stars for significance
                    local stars ""
                    if `pval' < 0.01 local stars "***"
                    else if `pval' < 0.05 local stars "**"
                    else if `pval' < 0.10 local stars "*"
                    
                    display "  H`h': β=" %7.4f `b' " (se=" %6.4f `se' ") N=" %8.0fc `N' " `stars'"
                }
                else {
                    display "  H`h': ESTIMATION FAILED"
                    post single_results ("`role'") (`h') (.) (.) (.) (0)
                }
            }
            
            // Quick interpretation
            qui reghdfe F1_prod pct_growth_`role' var4, absorb(user_id firm_id yh) vce(cluster user_id)
            if _rc == 0 {
                local peak_effect = _b[pct_growth_`role']
                local effect_size = `peak_effect' * 50  // Effect of 50% growth
                display "  → 50% `role' growth changes productivity by " %5.2f `effect_size' " percentiles after 1 period"
            }
        }
        else {
            display "  INSUFFICIENT DATA (N = `n_role')"
            forvalues h = 0/4 {
                post single_results ("`role'") (`h') (.) (.) (.) (`n_role')
            }
        }
    }
    else {
        display _n "========== `role': VARIABLE NOT FOUND =========="
    }
}

postclose single_results

*============================================================*
* APPROACH 2: Multi-Variable Horse Race
*============================================================*

display _n _n "================================================================="
display "APPROACH 2: MULTI-VARIABLE HORSE RACE"
display "================================================================="

// Build list of available variables
local comp_vars ""
local role_list "Engineer Sales Marketing Finance Operations"
foreach role of local role_list {
    capture confirm variable pct_growth_`role'
    if _rc == 0 {
        count if !missing(pct_growth_`role')
        if r(N) > 1000 {
            local comp_vars "`comp_vars' pct_growth_`role'"
            display "Added `role' to horse race (N=" r(N) ")"
        }
    }
}

display "Horse race variables: `comp_vars'"

// Check correlations between variables
display _n "Correlation matrix:"
corr `comp_vars'

// Check joint sample size
local n_vars : word count `comp_vars'
if `n_vars' >= 2 {
    
    // Count complete cases
    local missing_condition ""
    foreach var of local comp_vars {
        if "`missing_condition'" == "" {
            local missing_condition "!missing(`var'"
        }
        else {
            local missing_condition "`missing_condition' & !missing(`var'"
        }
    }
    local missing_condition "`missing_condition' & !missing(total_contributions_q100, F4_prod)"
    
    count if `missing_condition'
    local n_joint = r(N)
    display "Joint analysis sample: " `n_joint'
    
    if `n_joint' > 5000 {
        
        // Setup results file for multi-variable analysis
        capture postfile multi_results str15 variable horizon coef se pval nobs ///
            using "$results/multi_variable_irfs.dta", replace
        
        display _n "Running multi-variable IRF..."
        
        forvalues h = 0/4 {
            capture reghdfe F`h'_prod `comp_vars' var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            
            if _rc == 0 {
                local N = e(N)
                display _n "Horizon `h' (N=" %8.0fc `N' "):"
                
                foreach var of local comp_vars {
                    local clean_name = subinstr("`var'", "pct_growth_", "", .)
                    local b = _b[`var']
                    local se = _se[`var']
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    
                    // Store results
                    post multi_results ("`clean_name'") (`h') (`b') (`se') (`pval') (`N')
                    
                    // Display with significance stars
                    local stars ""
                    if `pval' < 0.01 local stars "***"
                    else if `pval' < 0.05 local stars "**"
                    else if `pval' < 0.10 local stars "*"
                    
                    display "  `clean_name': β=" %7.4f `b' " (se=" %6.4f `se' ") `stars'"
                }
            }
            else {
                display "Horizon `h': ESTIMATION FAILED"
                foreach var of local comp_vars {
                    local clean_name = subinstr("`var'", "pct_growth_", "", .)
                    post multi_results ("`clean_name'") (`h') (.) (.) (.) (0)
                }
            }
        }
        
        postclose multi_results
        
        // Test joint significance
        display _n "Testing joint significance at each horizon..."
        forvalues h = 0/4 {
            capture reghdfe F`h'_prod `comp_vars' var4, absorb(user_id firm_id yh) vce(cluster user_id)
            if _rc == 0 {
                capture test `comp_vars'
                if _rc == 0 {
                    display "  H`h': F=" %6.2f r(F) " p-value=" %6.4f r(p)
                }
            }
        }
    }
    else {
        display "INSUFFICIENT JOINT SAMPLE (N = `n_joint')"
    }
}
else {
    display "INSUFFICIENT VARIABLES FOR HORSE RACE"
}

*============================================================*
* COMPARISON AND SUMMARY
*============================================================*

display _n _n "================================================================="
display "RESULTS COMPARISON AND RECOMMENDATIONS"
display "================================================================="

// Load single variable results for summary
capture use "$results/single_variable_irfs.dta", clear
if _rc == 0 {
    display _n "SINGLE-VARIABLE APPROACH SUMMARY:"
    display "Role with strongest H1 effect (peak spillover):"
    keep if horizon == 1 & coef != .
    gsort -coef
    display "  1. " role[1] ": β=" %6.3f coef[1] " (se=" %6.3f se[1] ")"
    if _N > 1 display "  2. " role[2] ": β=" %6.3f coef[2] " (se=" %6.3f se[2] ")"
    if _N > 2 display "  3. " role[3] ": β=" %6.3f coef[3] " (se=" %6.3f se[3] ")"
}

// Load multi-variable results for summary
capture use "$results/multi_variable_irfs.dta", clear
if _rc == 0 {
    display _n "MULTI-VARIABLE APPROACH SUMMARY:"
    display "Variables with significant H1 effects in horse race:"
    keep if horizon == 1 & coef != . & pval < 0.10
    if _N > 0 {
        gsort -coef
        forvalues i = 1/`=min(_N,5)' {
            local stars ""
            if pval[`i'] < 0.01 local stars "***"
            else if pval[`i'] < 0.05 local stars "**"
            else if pval[`i'] < 0.10 local stars "*"
            display "  " variable[`i'] ": β=" %6.3f coef[`i'] " (p=" %5.3f pval[`i'] ") `stars'"
        }
    }
    else {
        display "  No significant effects in horse race"
    }
}

display _n "RECOMMENDATION:"
display "Both approaches appear feasible with this dataset."
display "Results saved in: $results/"
display "Next steps: Compare coefficient patterns and statistical power."

log close