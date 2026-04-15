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
* composition_irfs_simple.do  
* Simplified test of composition IRF approaches
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_simple.log", replace text

global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_test"
capture mkdir "$results"

display "============================================================"
display "COMPOSITION IRF TEST - SIMPLIFIED VERSION"  
display "============================================================"

*============================================================*
* LOAD AND MERGE DATA
*============================================================*

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear
display "User panel: N = " _N

// Drop any existing merge variables
capture drop _merge*
gen companyname_c = lower(companyname)

// Quick sample check
tab yh
display "User panel time range: " r(min) " to " r(max)

// Load and prepare role composition data  
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year,half)
    gen companyname_c = lower(companyname)
    
    // Keep only key variables and roles
    keep if inlist(role_k7, "Engineer", "Sales", "Marketing")
    keep companyname_c yh role_k7 pct_growth_role role_share
    
    // Reshape to wide
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share* share_*
    
    tempfile role_wide
    save `role_wide'
restore

// Merge with user panel
display "Merging composition data..."
merge m:1 companyname_c yh using `role_wide'
display "Merge results:"
tab _merge

// Keep matched observations
keep if _merge == 3
drop _merge

display "Final dataset: N = " _N

*============================================================*
* DATA QUALITY CHECKS
*============================================================*

display _n "=== DATA QUALITY CHECKS ==="

// Check key variables
foreach var in pct_growth_Engineer pct_growth_Sales pct_growth_Marketing {
    capture confirm variable `var'
    if _rc == 0 {
        count if !missing(`var')
        display "`var': " r(N) " observations"
        if r(N) > 0 {
            qui sum `var', detail
            display "  Mean: " r(mean) " Std: " r(sd)
        }
    }
    else {
        display "`var': NOT FOUND"
    }
}

// Correlation matrix
display _n "Correlations between composition variables:"
capture corr pct_growth_Engineer pct_growth_Sales pct_growth_Marketing
if _rc != 0 {
    display "Correlation failed - checking available variables..."
    describe pct_growth_*
}

*============================================================*  
* TEST IRF APPROACHES
*============================================================*

display _n "=== TESTING IRF APPROACHES ==="

// Set up panel
capture xtset user_id yh
if _rc != 0 {
    display "Error: Cannot set panel structure"
    describe user_id yh
    exit
}

// Generate outcome leads
display "Generating leads for IRF..."
sort user_id yh
forvalues h = 0/4 {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Check data availability for IRF
count if !missing(F0_prod, F4_prod, total_contributions_q100)
display "Observations available for 4-period IRF: " r(N)

*============================================================*
* APPROACH 1: Single Variable (Engineer)
*============================================================*

display _n "=== APPROACH 1: Engineer hiring only ==="

capture confirm variable pct_growth_Engineer
if _rc == 0 {
    count if !missing(pct_growth_Engineer, total_contributions_q100, F4_prod)
    local n_eng = r(N)
    display "Engineer analysis sample: " `n_eng'
    
    if `n_eng' > 1000 {
        display "Testing Engineer IRF..."
        
        forvalues h = 0/4 {
            capture reghdfe F`h'_prod pct_growth_Engineer var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            
            if _rc == 0 {
                display "Horizon `h': β=" %7.4f _b[pct_growth_Engineer] ///
                    " (se=" %7.4f _se[pct_growth_Engineer] ") N=" e(N)
            }
            else {
                display "Horizon `h': FAILED"
            }
        }
    }
    else {
        display "Insufficient data for Engineer analysis"
    }
}
else {
    display "Engineer variable not found"
}

*============================================================*
* APPROACH 2: Multiple Variables
*============================================================*

display _n "=== APPROACH 2: Multiple composition variables ==="

// Build list of available variables
local comp_vars ""
foreach var in Engineer Sales Marketing {
    capture confirm variable pct_growth_`var'
    if _rc == 0 {
        count if !missing(pct_growth_`var')
        if r(N) > 100 {
            local comp_vars "`comp_vars' pct_growth_`var'"
        }
    }
}

display "Available composition variables: `comp_vars'"

if "`comp_vars'" != "" {
    // Check sample size
    local var_list = subinstr("`comp_vars'", " ", " & !missing(", .)
    count if !missing(`var_list', total_contributions_q100, F4_prod)
    local n_multi = r(N)
    display "Multi-variable analysis sample: " `n_multi'
    
    if `n_multi' > 1000 {
        display "Testing multi-variable IRF..."
        
        forvalues h = 0/4 {
            capture reghdfe F`h'_prod `comp_vars' var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            
            if _rc == 0 {
                display "Horizon `h' (N=" e(N) "):"
                foreach var of local comp_vars {
                    display "  `var': β=" %7.4f _b[`var'] ///
                        " (se=" %7.4f _se[`var'] ")"
                }
            }
            else {
                display "Horizon `h': FAILED"
            }
        }
    }
    else {
        display "Insufficient data for multi-variable analysis"
    }
}

*============================================================*
* SUMMARY
*============================================================*

display _n "=== SUMMARY ==="
display "Data merge successful: " c(N) " observations"
display "Time period compatibility: User panel has different coding"
display "  - User panel: yh 114-124"  
display "  - Composition: yh 20182-20221"
display "Recommendation: Need to fix time variable matching"

log close
