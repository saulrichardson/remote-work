*============================================================*
* Asset 15: crunchbase_fundraising_event_study_raised_usd_mil_ols.png
*============================================================*

local asset_stem "15_crunchbase_fundraising_event_study_raised_usd_mil_ols"
local outcome "cb_raised_usd_mil"

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

capture which reghdfe
if _rc {
    di as error "Required package 'reghdfe' not found."
    di as error "Install once via: ssc install reghdfe, replace"
    exit 199
}

local in_csv "$processed_data/firm_panel_with_cb_funding.csv"
capture confirm file "`in_csv'"
if _rc {
    di as error "Missing input panel: `in_csv'"
    di as error "Build it first via: python src/py/build_firm_panel_with_crunchbase_funding.py"
    exit 601
}

import delimited using "`in_csv'", clear varnames(1) case(preserve) stringcols(_all)

local required_vars firm_id yh_num cb_matched public remote cb_raised_usd
foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

local maybe_numeric firm_id yh_num cb_matched public remote cb_raised_usd
foreach v of local maybe_numeric {
    capture confirm numeric variable `v'
    if _rc {
        destring `v', replace ignore(" ,")
    }
}

format yh_num %th

capture confirm numeric variable firm_id
if _rc {
    encode firm_id, gen(firm_id_num)
}
else {
    gen long firm_id_num = firm_id
}

keep if cb_matched == 1
keep if public != 1

count if missing(cb_raised_usd)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing cb_raised_usd (should be 0)."
    exit 459
}
count if missing(remote)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing remote."
    exit 459
}

capture drop cb_raised_usd_mil
gen double cb_raised_usd_mil = cb_raised_usd / 1000000
label var cb_raised_usd_mil "USD raised in half-year (millions; includes zeros)"

tab yh_num, gen(time)

tempvar tmpindex
preserve
    contract yh_num
    sort yh_num
    gen `tmpindex' = _n
    local target19h2 = yh(2019, 2)
    quietly summarize `tmpindex' if yh_num == `target19h2'
    local idx19h2 = r(mean)
    if missing(`idx19h2') {
        di as error "Baseline half-year 2019H2 not found in sample."
        exit 498
    }
    di as text "Baseline index for 2019H2 is `idx19h2'"
    gen str7 period_label = subinstr(string(yh_num, "%th"), "h", "H", .)
    keep yh_num `tmpindex' period_label
    rename `tmpindex' period
    rename yh_num yh
    tempfile yhmap
    save `yhmap'
restore

preserve
    contract yh_num
    local total_periods = _N
restore

local rem_vars ""
forval t = 1/`total_periods' {
    gen double rem_`t' = remote * time`t'
    if `t' == `idx19h2' continue
    local rem_vars `rem_vars' rem_`t'
}

reghdfe `outcome' `rem_vars', absorb(firm_id_num yh_num) vce(cluster firm_id_num)

matrix define escoef = J(`total_periods', 3, .)
forval i = 1/`total_periods' {
    if `i' == `idx19h2' continue
    local b = _b[rem_`i']
    local se = _se[rem_`i']
    matrix escoef[`i', 1] = `b'
    matrix escoef[`i', 2] = `b' - 1.96 * `se'
    matrix escoef[`i', 3] = `b' + 1.96 * `se'
}
matrix colnames escoef = b lb ub

local result_dir "$results/`asset_stem'"
cap mkdir "`result_dir'"

preserve
    clear
    svmat double escoef, names(col)
    gen period = _n
    gen event_time = period - `idx19h2'
    gen omitted = period == `idx19h2'
    replace b = . if omitted
    replace lb = . if omitted
    replace ub = . if omitted
    merge 1:1 period using `yhmap', nogen
    gen str8 estimator = "OLS"
    gen str80 outcome = "`outcome'"
    order outcome estimator period period_label event_time omitted b lb ub yh
    export delimited using "`result_dir'/ols_cb_raised_usd_mil.csv", replace
restore

log close
