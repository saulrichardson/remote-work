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
* Run just the fixed shares analysis 
*============================================================*

clear all
set more off

// Globals
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "user_productivity_composition"
local result_dir "$results/`specname'"

// Load and prepare data
use "$processed_data/user_panel_precovid.dta", clear
tempfile user_data
save `user_data'

import delimited "$processed_data/role_k7_scaling_growth.csv", clear
gen yh = yh(year, half)
keep companyname yh role_k7 role_share
reshape wide role_share, i(companyname yh) j(role_k7) string
rename role_share* share_*
tempfile role_share_wide
save `role_share_wide'

// CORRECTED Part A2: Role Composition Controls (Shares)
use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `role_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

// FIXED zero-fill logic
capture unab sharevars: share_*
if _rc == 0 {
    foreach v of local sharevars {
        quietly replace `v' = 0 if missing(`v')
    }
}

// Set up results collection
capture postclose handle_role_sh
tempfile out_role_sh
postfile handle_role_sh str20 role str8 model_type str40 param double coef se pval pre_mean nobs rkf using `out_role_sh', replace

local roles "Admin Engineer Finance Marketing Operations Sales Scientist"

// Baseline
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)
reghdfe total_contributions_q100 var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_role_sh ("Baseline") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
}
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_role_sh ("Baseline") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
}

// Role-specific regressions
foreach role in `roles' {
    capture confirm variable share_`role'
    if _rc == 0 {
        gen `role'_share_covid = covid * share_`role'
        gen `role'_share_inter = covid * share_`role' * startup

        count if !missing(share_`role') & !missing(total_contributions_q100)
        summarize total_contributions_q100 if covid == 0, meanonly
        local pre_mean = r(mean)

        // OLS
        reghdfe total_contributions_q100 var3 var5 var4 `role'_share_covid `role'_share_inter, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        local N = e(N)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_role_sh ("`role'") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        local b = _b[`role'_share_inter]
        local se = _se[`role'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_role_sh ("`role'") ("OLS") ("`role'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (.)

        // IV
        ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 `role'_share_covid `role'_share_inter, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        local N = e(N)
        local rkf = e(rkf)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_role_sh ("`role'") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
        local b = _b[`role'_share_inter]
        local se = _se[`role'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_role_sh ("`role'") ("IV") ("`role'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')

        drop `role'_share_covid `role'_share_inter
    }
}

// Save results
postclose handle_role_sh
use `out_role_sh', clear
export delimited using "`result_dir'/role_composition_share_results_fixed.csv", replace
save "`result_dir'/role_composition_share_results_fixed.dta", replace

display "Fixed role share results saved!"