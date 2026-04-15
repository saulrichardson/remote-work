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
* composition_irfs_test.do
* Test different approaches for composition IRFs
* Compare data demands and estimation feasibility
*============================================================*

clear all
set more off

// Setup
capture log close
log using "composition_irfs_test.log", replace text

// Globals
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_test"
capture mkdir "$results"

display "============================================================"
display "COMPOSITION IRF FEASIBILITY TEST"
display "============================================================"

*============================================================*
* STEP 1: Load and merge data
*============================================================*

display _n "STEP 1: Loading user productivity panel..."
use "$processed_data/user_panel_precovid.dta", clear
display "User panel loaded: N = " _N

// Drop any existing merge variable
capture drop _merge

// Create company name key for merging
gen companyname_c = lower(companyname)

// Check sample period
summarize yh, detail
display "User panel time range: " r(min) " to " r(max)

display _n "STEP 1b: Loading composition data..."
// Load role composition data
import delimited "$processed_data/role_k7_scaling_growth.csv", clear

// Convert time variable to match user panel
gen yh = year*10 + half
display "Composition data time range: " yh[1] " to " yh[_N]

// Create company key
gen companyname_c = lower(companyname)

// Reshape to wide format for merging
display "Reshaping composition data to wide format..."
keep companyname_c yh role_k7 pct_growth_role role_share
reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string

// Clean variable names
rename pct_growth_role* pct_growth_*
rename role_share* share_*

// Save as tempfile
tempfile role_comp_wide
save `role_comp_wide'

// Load seniority composition data
display "Loading seniority composition data..."
import delimited "$processed_data/seniority_scaling_growth.csv", clear
gen yh = year*10 + half
gen companyname_c = lower(companyname)

// Reshape seniority data
keep companyname_c yh seniority_level pct_growth_seniority seniority_share
gen sen_label = "sen" + string(seniority_level)
drop seniority_level

reshape wide pct_growth_seniority seniority_share, i(companyname_c yh) j(sen_label) string
rename pct_growth_seniority* pct_growth_*
rename seniority_share* share_*

tempfile sen_comp_wide
save `sen_comp_wide'

*============================================================*
* STEP 2: Merge with user panel
*============================================================*

display _n "STEP 2: Merging composition data with user panel..."
use "$processed_data/user_panel_precovid.dta", clear
gen companyname_c = lower(companyname)

// Merge role composition
display "Merging role composition..."
merge m:1 companyname_c yh using `role_comp_wide'
display "Role composition merge results:"
tab _merge
drop _merge

// Merge seniority composition  
display "Merging seniority composition..."
merge m:1 companyname_c yh using `sen_comp_wide'
display "Seniority composition merge results:"
tab _merge
drop _merge

display "Final merged dataset: N = " _N

*============================================================*
* STEP 3: Data quality checks
*============================================================*

display _n "STEP 3: Data quality assessment..."

// Check available composition variables
display "Available role composition variables:"
describe pct_growth_*, simple

display "Available seniority composition variables:"
describe pct_growth_sen*, simple

// Count non-missing observations for key variables
local key_vars "pct_growth_Engineer pct_growth_Sales pct_growth_Marketing pct_growth_sen3 pct_growth_sen4"
foreach var of local key_vars {
    capture confirm variable `var'
    if _rc == 0 {
        count if !missing(`var')
        display "`var': " r(N) " non-missing observations"
    }
    else {
        display "`var': VARIABLE NOT FOUND"
    }
}

// Correlation matrix
display _n "Correlation matrix of composition variables:"
capture {
    corr pct_growth_Engineer pct_growth_Sales pct_growth_Marketing pct_growth_sen3 pct_growth_sen4 if !missing(total_contributions_q100)
}
if _rc != 0 {
    display "Some variables missing - checking available variables..."
    corr pct_growth_* if !missing(total_contributions_q100)
}

*============================================================*
* STEP 4: Test different IRF approaches
*============================================================*

display _n "STEP 4: Testing IRF approaches..."

// Set panel structure
capture xtset user_id yh
if _rc != 0 {
    display "Panel structure setup failed - checking data structure"
    isid user_id yh
}

// Generate outcome leads
display "Generating outcome leads for IRF..."
sort user_id yh
forvalues h = 0/4 {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Check how many observations we have for IRF estimation
count if !missing(F0_prod, F4_prod)
display "Observations available for full 4-period IRF: " r(N)

*============================================================*
* APPROACH 1: Single composition variable (Engineer)
*============================================================*

display _n "APPROACH 1: Engineer hiring effects only..."

// Check if engineer variable exists and has variation
capture confirm variable pct_growth_Engineer
if _rc == 0 {
    summarize pct_growth_Engineer, detail
    display "Engineer growth: mean=" r(mean) " sd=" r(sd) " N=" r(N)
    
    if r(sd) > 0 & r(N) > 1000 {
        display "Testing single-variable IRF..."
        
        capture postfile eng_results horizon coef se pval nobs using "$results/engineer_irf.dta", replace
        
        forvalues h = 0/4 {
            capture reghdfe F`h'_prod pct_growth_Engineer var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            
            if _rc == 0 {
                local b = _b[pct_growth_Engineer]
                local se = _se[pct_growth_Engineer]
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                local N = e(N)
                
                display "  Horizon `h': β=" %8.4f `b' " (se=" %8.4f `se' ") N=" `N'
                post eng_results (`h') (`b') (`se') (`pval') (`N')
            }
            else {
                display "  Horizon `h': Estimation failed"
            }
        }
        postclose eng_results
        display "Engineer IRF results saved to: $results/engineer_irf.dta"
    }
    else {
        display "Insufficient variation in Engineer growth variable"
    }
}
else {
    display "Engineer growth variable not found"
}

*============================================================*
* APPROACH 2: Multiple composition variables
*============================================================*

display _n "APPROACH 2: Multiple composition variables..."

// Build list of available composition variables
local comp_vars ""
local var_names "Engineer Sales Marketing"
foreach var of local var_names {
    capture confirm variable pct_growth_`var'
    if _rc == 0 {
        count if !missing(pct_growth_`var')
        if r(N) > 100 {
            local comp_vars "`comp_vars' pct_growth_`var'"
            display "Added pct_growth_`var' (N=" r(N) ")"
        }
    }
}

// Add seniority variables
foreach sen in sen3 sen4 {
    capture confirm variable pct_growth_`sen'
    if _rc == 0 {
        count if !missing(pct_growth_`sen')
        if r(N) > 100 {
            local comp_vars "`comp_vars' pct_growth_`sen'"
            display "Added pct_growth_`sen' (N=" r(N) ")"
        }
    }
}

display "Final composition variable list: `comp_vars'"

if "`comp_vars'" != "" {
    // Check multicollinearity
    display "Correlation matrix for selected variables:"
    corr `comp_vars' if !missing(total_contributions_q100)
    
    // Test multi-variable IRF
    display "Testing multi-variable IRF..."
    
    capture postfile multi_results str20 variable horizon coef se pval nobs using "$results/multi_irf.dta", replace
    
    forvalues h = 0/4 {
        capture reghdfe F`h'_prod `comp_vars' var4, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        
        if _rc == 0 {
            local N = e(N)
            display "  Horizon `h' results (N=" `N' "):"
            
            foreach var of local comp_vars {
                local b = _b[`var']
                local se = _se[`var']
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                
                display "    `var': β=" %8.4f `b' " (se=" %8.4f `se' ")"
                post multi_results ("`var'") (`h') (`b') (`se') (`pval') (`N')
            }
        }
        else {
            display "  Horizon `h': Estimation failed - likely insufficient data"
        }
    }
    postclose multi_results
    display "Multi-variable IRF results saved to: $results/multi_irf.dta"
}
else {
    display "No composition variables available for multi-variable analysis"
}

*============================================================*
* SUMMARY AND RECOMMENDATIONS
*============================================================*

display _n "============================================================"
display "SUMMARY AND RECOMMENDATIONS"
display "============================================================"

// Data availability summary
display "Data merge success:"
count
display "  Total observations after merge: " r(N)

count if !missing(total_contributions_q100)
display "  Observations with productivity data: " r(N)

count if !missing(total_contributions_q100, F4_prod)
display "  Observations available for 4-period IRF: " r(N)

// Variable availability
display _n "Composition variables found:"
describe pct_growth_*, varlist
local found_vars r(varlist)
display "Found variables: `found_vars'"

// Feasibility assessment
count if !missing(total_contributions_q100, F4_prod) 
local n_complete = r(N)

if `n_complete' > 10000 {
    display _n "RECOMMENDATION: Data sufficient for IRF analysis"
    display "  - Use multi-variable approach if correlations reasonable"
    display "  - Consider heterogeneity analysis by worker type"
}
else if `n_complete' > 1000 {
    display _n "RECOMMENDATION: Limited data - use single-variable approach"
    display "  - Focus on most important composition variable (likely Engineer)"
}
else {
    display _n "WARNING: Insufficient data for reliable IRF analysis"
    display "  - Consider expanding time period or sample"
}

display _n "Results saved in: $results/"
display "Next steps: Review correlation matrices and IRF estimates"

log close