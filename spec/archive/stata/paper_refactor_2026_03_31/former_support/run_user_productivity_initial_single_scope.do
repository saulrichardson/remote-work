*============================================================*
* Narrow support helper for a single user-productivity asset.
* Exports only the requested outcome/model rows for the
* baseline no-startup-interaction specification.
*============================================================*

args panel_variant specname result_subdir outcome_name model_mode
if "`panel_variant'" == "" local panel_variant "precovid"
if "`specname'" == "" {
    di as error "run_user_productivity_initial_single_scope.do requires specname"
    exit 198
}
if "`result_subdir'" == "" {
    di as error "run_user_productivity_initial_single_scope.do requires result_subdir"
    exit 198
}
if "`outcome_name'" == "" {
    di as error "run_user_productivity_initial_single_scope.do requires outcome_name"
    exit 198
}
if "`model_mode'" == "" local model_mode "both"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

local result_dir "$results/`result_subdir'"
! /bin/mkdir -p "`result_dir'"

use "$processed_data/user_panel_`panel_variant'.dta", clear

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome    ///
    str40  param      ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

summarize `outcome_name' if covid == 0, meanonly
local pre_mean = r(mean)

if inlist("`model_mode'", "ols", "both") {
    reghdfe `outcome_name' var3 var4, absorb(user_id firm_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }
}

if inlist("`model_mode'", "iv", "both") {
    ivreghdfe ///
        `outcome_name' (var3 = var6) var4, ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
di as result "→ CSV: `result_dir'/consolidated_results.csv"
capture log close
