*============================================================*
* Asset 05: firm_event_study_join_rate_ols.png
*============================================================*

local asset_stem "05_firm_event_study_join_rate_ols"
local outcome "join_rate_we"

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
log using "$LOG_DIR/`asset_stem'.log", replace text

local result_dir "$results/`asset_stem'"
cap mkdir "`result_dir'"

use "$processed_data/firm_panel.dta", clear
tab yh, gen(time)

tempvar tmpindex
preserve
    contract yh
    sort yh
    gen `tmpindex' = _n
    local target19h2 = yh(2019, 2)
    quietly summarize `tmpindex' if yh == `target19h2'
    local idx19h2 = r(mean)
    gen str7 period_label = subinstr(string(yh, "%th"), "h", "H", .)
    keep yh `tmpindex' period_label
    rename `tmpindex' period
    tempfile yhmap
    save `yhmap'
restore

preserve
    contract yh
    local total_periods = _N
restore

local rem_vars ""
local rem_start_vars ""
local startup_vars ""
forval t = 1/`total_periods' {
    gen rem_`t'       = remote * time`t'
    gen startup_`t'   = startup * time`t'
    gen rem_start_`t' = remote * time`t' * startup
    if `t' == `idx19h2' continue
    local rem_vars `rem_vars' rem_`t'
    local rem_start_vars `rem_start_vars' rem_start_`t'
    local startup_vars `startup_vars' startup_`t'
}

reghdfe `outcome' `rem_vars' `rem_start_vars' `startup_vars', absorb(firm_id yh) cluster(firm_id)

matrix define escoef = J(`total_periods',3,.)
forval i = 1/`total_periods' {
    if `i' == `idx19h2' continue
    local b = _b[rem_start_`i']
    local se = _se[rem_start_`i']
    matrix escoef[`i',1] = `b'
    matrix escoef[`i',2] = `b' - 1.96*`se'
    matrix escoef[`i',3] = `b' + 1.96*`se'
}
matrix colnames escoef = b lb ub

preserve
    clear
    svmat double escoef, names(col)
    gen period     = _n
    gen event_time = period - `idx19h2'
    gen omitted    = period == `idx19h2'
    replace b = . if omitted
    replace lb = . if omitted
    replace ub = . if omitted
    merge 1:1 period using `yhmap', nogen
    gen str8 estimator = "OLS"
    gen str80 outcome = "`outcome'"
    order outcome estimator period period_label event_time omitted b lb ub yh
    export delimited using "`result_dir'/ols_join_rate_we.csv", replace
restore

log close
