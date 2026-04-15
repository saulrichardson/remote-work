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
* composition_irfs_multi_fixed.do
* Run the multi-variable approach with fixed syntax
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_multi_fixed.log", replace text

global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_test"

display "============================================================"
display "MULTI-VARIABLE IRF ANALYSIS - FIXED VERSION"
display "============================================================"

// Load merged data (repeat setup from successful script)
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)

preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year,half)
    gen companyname_c = lower(companyname)
    keep if inlist(role_k7, "Engineer", "Sales", "Marketing", "Finance", "Operations")
    keep companyname_c yh role_k7 pct_growth_role role_share
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share* share_*
    tempfile role_wide
    save `role_wide'
restore

merge m:1 companyname_c yh using `role_wide'
keep if _merge == 3
drop _merge

// Setup panel and leads
xtset user_id yh
sort user_id yh
forvalues h = 0/4 {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

display "Setup complete, N = " _N

// Multi-variable analysis with all 5 roles
local comp_vars "pct_growth_Engineer pct_growth_Sales pct_growth_Marketing pct_growth_Finance pct_growth_Operations"

// Check joint sample size (fixed syntax)
count if !missing(pct_growth_Engineer, pct_growth_Sales, pct_growth_Marketing, pct_growth_Finance, pct_growth_Operations, total_contributions_q100, F4_prod)
local n_joint = r(N)
display "Joint analysis sample: " `n_joint'

// Correlation matrix
display _n "Correlation matrix:"
corr `comp_vars'

// Setup results storage
capture postfile multi_results str15 variable horizon coef se pval nobs ///
    using "$results/multi_variable_irfs_fixed.dta", replace

if `n_joint' > 5000 {
    display _n "Running multi-variable horse race..."
    
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
                
                post multi_results ("`clean_name'") (`h') (`b') (`se') (`pval') (`N')
                
                local stars ""
                if `pval' < 0.01 local stars "***"
                else if `pval' < 0.05 local stars "**"
                else if `pval' < 0.10 local stars "*"
                
                display "  `clean_name': β=" %7.4f `b' " (se=" %6.4f `se' ") `stars'"
            }
        }
        else {
            display "Horizon `h': FAILED"
        }
    }
    
    // Test joint significance
    display _n "Joint significance tests:"
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
    display "Insufficient joint sample size"
}

postclose multi_results

log close