*============================================================*
* firm_scaling_github_users.do
*
* Runs the baseline firm_scaling regression specification, but on a firm panel
* where growth/join/leave outcomes are computed *only* from the GitHub-linked
* user sample (see src/stata/build_firm_panel_github_users.do).
*
* Usage:
*   do src/stata/build_firm_panel_github_users.do [user_variant]
*   do spec/stata/firm_scaling_github_users.do   [user_variant]
*
* Example:
*   do src/stata/build_firm_panel_github_users.do precovid
*   do spec/stata/firm_scaling_github_users.do precovid
*
* Output:
*   results/raw/firm_scaling_github_users_<variant>/
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional user-panel variant argument
* --------------------------------------------------------------------------
args user_variant
if "`user_variant'" == "" local user_variant "precovid"
local specname "firm_scaling_github_users_`user_variant'"

* --------------------------------------------------------------------------
* 1) Bootstrap paths + logging
* --------------------------------------------------------------------------
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

* Dependency checks (fail fast) --------------------------------------------
capture which reghdfe
if _rc {
    di as error "Required package 'reghdfe' not found."
    di as error "Install once via:  ssc install reghdfe, replace"
    exit 199
}
capture which ivreghdfe
if _rc {
    di as error "Required package 'ivreghdfe' not found."
    di as error "Install once via:  ssc install ivreghdfe, replace"
    exit 199
}

* --------------------------------------------------------------------------
* 2) Load GitHub-user firm panel
* --------------------------------------------------------------------------
capture confirm file "$processed_data/firm_panel_github_users_`user_variant'.dta"
if _rc {
    di as error "Missing GitHub-user firm panel: $processed_data/firm_panel_github_users_`user_variant'.dta"
    di as error "Run src/stata/build_firm_panel_github_users.do `user_variant' first."
    exit 601
}

use "$processed_data/firm_panel_github_users_`user_variant'.dta", clear

foreach v in firm_id yh covid growth_rate_we join_rate_we leave_rate_we var3 var4 var5 var6 var7 {
    cap confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in GitHub-user firm panel."
        exit 198
    }
}

* --------------------------------------------------------------------------
* 3) Results setup (postfiles)
* --------------------------------------------------------------------------
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

* --------------------------------------------------------------------------
* 4) Main regressions (mirrors firm_scaling.do)
* --------------------------------------------------------------------------
local outcome_vars growth_rate_we join_rate_we leave_rate_we
local fs_done = 0

foreach y of local outcome_vars {
    di as text "→ Processing `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    * --- OLS ---
    reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    * --- IV (2nd stage) ---
    ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst

    local rkf = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    * --- FIRST STAGE (once) ---
    if !`fs_done' {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        estimates restore _ivreg2_var3
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var3") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F3') (`rkf') (`N_fs')
        }

        estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var5") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F5') (`rkf') (`N_fs')
        }

        local fs_done 1
    }
}

* --------------------------------------------------------------------------
* 5) Export
* --------------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
capture log close
