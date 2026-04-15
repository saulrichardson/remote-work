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



* --------------------------------------------------------------------------
* User productivity: binary remote (remote==1) vs hybrid/in-person (remote<1)
* --------------------------------------------------------------------------

args panel_variant treat
if "`panel_variant'" == "" local panel_variant "precovid"
if "`treat'"         == "" local treat         "remote"

local specname user_productivity_binary_`panel_variant'_`treat'
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local cwd = c(pwd)
if !regexm("`cwd'", "/spec$") {
    cd spec
}

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome   ///
    str40  param     ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

// Construct the binary treatment
if "`treat'" == "remote" {
    capture drop var3_remote var5_remote
    gen byte flag_remote = remote == 1
    gen var3_remote = flag_remote * covid
    gen var5_remote = flag_remote * covid * startup
    local v3 var3_remote
    local v5 var5_remote
}
else if "`treat'" == "nonremote" {
    capture drop var3_nonremote var5_nonremote
    gen byte flag_nonremote = remote < 1
    gen var3_nonremote = flag_nonremote * covid
    gen var5_nonremote = flag_nonremote * covid * startup
    local v3 var3_nonremote
    local v5 var5_nonremote
}
else {
    di as error "Unknown treat=`treat'—must be remote or nonremote"
    exit 1
}

local outcomes total_contributions_q100

foreach y of local outcomes {
    di as text "→ outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS regression
    reghdfe `y' `v3' `v5' var4, absorb(user_id#firm_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in `v3' `v5' var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle ("OLS") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    // IV regression
    ivreghdfe `y' (`v3' `v5' = var6 var7) var4, absorb(user_id#firm_id yh) vce(cluster user_id)
    local rkf = e(rkf)
    local N = e(N)
    foreach p in `v3' `v5' var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle ("IV") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"

capture log close
