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
* scaling_composition_roles.do
* Role-specific scaling regressions
*============================================================*

clear all
set more off

// Set up log
capture log close
log using "scaling_composition_roles.log", replace text

// Globals and setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "scaling_composition_roles"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

display "============================================================"
display "Starting Scaling Composition Roles Analysis"
display "============================================================"

// Load role growth/share data first
import delimited "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/role_k7_scaling_growth.csv", clear

// Create yh variable using Stata's yh() function
gen yh = yh(year, half)

// Clean role names (remove spaces/quotes)
replace role_k7 = subinstr(role_k7, " ", "", .)
replace role_k7 = subinstr(role_k7, `"""', "", .)

// Keep copy for growth reshape
preserve
    keep companyname yh role_k7 pct_growth_role
    rename pct_growth_role pct_growth_
    reshape wide pct_growth_, i(companyname yh) j(role_k7) string
    tempfile role_growth
    save `role_growth'
restore

// Build share-wide dataset
keep companyname yh role_k7 role_share
rename role_share share_
reshape wide share_, i(companyname yh) j(role_k7) string
tempfile role_share_wide
save `role_share_wide'

// Load firm panel
use "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/firm_panel.dta", clear

// Merge with growth data (now 1:1 merge at firm-yh level)
merge 1:1 companyname yh using `role_growth'
keep if _merge == 3
drop _merge

// Set up postfile for results
capture postclose handle_role
tempfile out_role
postfile handle_role ///
    str20  role ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_role', replace

// Run regression for each role
local roles "Admin Engineer Finance Marketing Operations Sales Scientist"
foreach role in `roles' {
    capture confirm variable pct_growth_`role'
    if _rc == 0 {
        di _n "========================================"
        di "Role: `role'"
        di "========================================"
        
        // Count non-missing observations
        count if !missing(pct_growth_`role')
        di "Non-missing observations: " r(N)
        
        // Calculate pre-COVID mean
        sum pct_growth_`role' if covid == 0
        local pre_mean = r(mean)
        di "Pre-COVID mean: " `pre_mean'
        
        // OLS regression
        reghdfe pct_growth_`role' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        
        // Store OLS results
        foreach p in var3 var5 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_role ("`role'") ("OLS") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        
        // IV regression
        ivreghdfe pct_growth_`role' (var3 var5 = var6 var7) var4, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        local rkf = e(rkf)
        
        // Store IV results
        foreach p in var3 var5 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_role ("`role'") ("IV") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
    }
}

// Save results
postclose handle_role
use `out_role', clear
export delimited using "`result_dir'/role_scaling_results.csv", replace
save "`result_dir'/role_scaling_results.dta", replace

// =====================
// Share-based outcomes
// =====================

// Merge share data
use "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/firm_panel.dta", clear
merge 1:1 companyname yh using `role_share_wide'
keep if _merge == 3
drop _merge

// FIXED zero-fill logic for roles
capture unab rvars: share_*
if _rc == 0 {
    foreach v of local rvars {
        quietly replace `v' = 0 if missing(`v')
    }
}

capture postclose handle_role_sh
tempfile out_role_sh
postfile handle_role_sh ///
    str20  role ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_role_sh', replace

// Run regression for each role share
local roles "Admin Engineer Finance Marketing Operations Sales Scientist"
foreach role in `roles' {
    capture confirm variable share_`role'
    if _rc == 0 {
        di _n "Share outcome — Role: `role'"
        count if !missing(share_`role')
        sum share_`role' if covid == 0
        local pre_mean = r(mean)

        // OLS
        reghdfe share_`role' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        local N = e(N)
        foreach p in var3 var5 var4 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_role_sh ("`role'") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }

        // IV
        ivreghdfe share_`role' (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
        local N = e(N)
        local rkf = e(rkf)
        foreach p in var3 var5 var4 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_role_sh ("`role'") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
    }
}

postclose handle_role_sh
use `out_role_sh', clear
export delimited using "`result_dir'/role_scaling_share_results.csv", replace
save "`result_dir'/role_scaling_share_results.dta", replace

display _n "============================================================"
display "Scaling Composition Roles Analysis Complete"
display "============================================================"
display "Results saved in: `result_dir'/"
display "  - role_scaling_results.csv"
display "  - role_scaling_results.dta"
display "Central log: scaling_composition_roles.log"

log close
