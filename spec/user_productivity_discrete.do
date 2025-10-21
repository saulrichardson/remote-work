
* --------------------------------------------------------------------------
* User productivity discrete specification: binary remote split
*   • Panel variants: unbalanced | balanced | precovid | balanced_pre
*   • Treatments : remote (=1) vs nonremote (<1)
* --------------------------------------------------------------------------

args panel_variant treat
if "`panel_variant'" == "" local panel_variant "precovid"
if "`treat'"         == "" local treat         "remote"

local specname user_productivity_`panel_variant'_`treat'

capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

// Setup environment
do "../src/globals.do"

// Load worker-level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear

// Prepare output directory
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

// First-stage capture
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar ///
    str40  param   ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

// Construct treatment
if "`treat'" == "remote" {
    tempvar flag
    capture drop var3_remote var5_remote
    gen byte `flag' = remote == 1
    gen var3_remote = `flag' * covid
    gen var5_remote = `flag' * covid * startup
    local v3 "var3_remote"
    local v5 "var5_remote"
}
else if "`treat'" == "nonremote" {
    tempvar flag
    capture drop var3_nonremote var5_nonremote
    gen byte `flag' = remote < 1
    gen var3_nonremote = `flag' * covid
    gen var5_nonremote = `flag' * covid * startup
    local v3 "var3_nonremote"
    local v5 "var5_nonremote"
}
else {
    di as error "Unknown treat=`treat'—must be remote or nonremote"
    exit 1
}

local outcomes total_contributions_q100

foreach y of local outcomes {
    di as text "→ Processing outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
    reghdfe `y' `v3' `v5' var4, absorb(user_id#firm_id yh) vce(cluster user_id)
    local N = e(N)

    foreach p in `v3' `v5' var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    // IV second stage
    ivreghdfe `y' (`v3' `v5' = var6 var7) var4, absorb(user_id#firm_id yh) vce(cluster user_id) savefirst
    local rkf = e(rkf)
    local N = e(N)

    foreach p in `v3' `v5' var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }

    // First-stage exports
    estimates restore _ivreg2_var3
    if _rc { continue }
    matrix FS = e(first)
    local F3 = FS[4,1]
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_fs ("`v3'") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
    }

    estimates restore _ivreg2_var5
    if _rc { continue }
    matrix FS = e(first)
    local F5 = FS[4,1]
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_fs ("`v5'") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"

capture log close
