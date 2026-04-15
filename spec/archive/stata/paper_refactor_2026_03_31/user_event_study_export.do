* Export user event-study coefficients for downstream plotting -----------------
* Usage:  do spec/user_event_study_export.do [panel_variant]

* 0) Parse optional panel variant argument (default = precovid)
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname "user_event_study_`panel_variant'"

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



local result_path "$results/`specname'"
cap mkdir "`result_path'"



use "$processed_data/user_panel_`panel_variant'.dta", clear

tab yh, gen(time)

* Map half-year indices -------------------------------------------------------
preserve
contract yh, freq(count_yh)
sort yh
gen period_index = _n
label var period_index "Sequential half-year index"
tempfile period_lookup
save "`period_lookup'", replace
local total_periods = _N
restore

* Identify baseline index (2019H2) --------------------------------------------
tempvar tmpindex
preserve
contract yh
sort yh
gen `tmpindex' = _n
local target19h2 = yh(2019, 2)
quietly summarize `tmpindex' if yh == `target19h2'
local idx19h2 = r(mean)
restore

forval t = 1/`total_periods' {
    gen rem_`t'       = remote * time`t'
    gen startup_`t'   = startup * time`t'
    gen rem_start_`t' = remote * time`t' * startup
    gen tel_`t'       = company_teleworkable * time`t'
    gen tel_start_`t' = company_teleworkable * time`t' * startup
}

local endog_vars ""
local instr_vars ""
local startup_vars ""
forval t = 1/`total_periods' {
    if `t' == `idx19h2' continue
    local endog_vars  `endog_vars'  rem_`t' rem_start_`t'
    local instr_vars  `instr_vars'  tel_`t' tel_start_`t'
    local startup_vars `startup_vars' startup_`t'
}

local transformed_vars total_contributions_q100 restricted_contributions_q100
local models "ols iv"

foreach outcome of local transformed_vars {
    foreach model of local models {
        eststo clear
        if "`model'" == "ols" {
            reghdfe `outcome' `endog_vars' `startup_vars', absorb(user_id firm_id yh) vce(cluster user_id)
        }
        else {
            ivreghdfe `outcome' (`endog_vars' = `instr_vars') `startup_vars', absorb(user_id firm_id yh) vce(cluster user_id)
        }

        matrix define escoef1 = J(`total_periods',3,0)
        local before_idx = (`idx19h2' - 1)
        local after_idx  = (`idx19h2' + 1)

        forval i = 1/`before_idx' {
            matrix escoef1[`i',1] = _b[rem_start_`i']
            matrix escoef1[`i',2] = _b[rem_start_`i'] - _se[rem_start_`i']*1.96
            matrix escoef1[`i',3] = _b[rem_start_`i'] + _se[rem_start_`i']*1.96
        }
        forval i = `after_idx'/`total_periods' {
            matrix escoef1[`i',1] = _b[rem_start_`i']
            matrix escoef1[`i',2] = _b[rem_start_`i'] - _se[rem_start_`i']*1.96
            matrix escoef1[`i',3] = _b[rem_start_`i'] + _se[rem_start_`i']*1.96
        }
        matrix colnames escoef1 = coef ci_low ci_high

        preserve
        clear
        svmat double escoef1, names(col)
        gen period_index = _n
        merge 1:1 period_index using "`period_lookup'", nogen
        gen byte base_period = (period_index == `idx19h2')
        gen rel_period = period_index - `idx19h2'
        gen outcome = "`outcome'"
        gen model   = "`model'"
        gen effect  = "remote_startup"
        gen panel_variant = "`panel_variant'"
        format yh %th
        gen str12 yh_label = string(yh, "%th")
        gen omitted = base_period

        rename coef b
        rename ci_low lb
        rename ci_high ub
        rename period_index period
        rename rel_period event_time

        order outcome model period period_label event_time omitted b lb ub yh yh_label panel_variant effect
        drop effect panel_variant

        local fname "`result_path'/`model'_`outcome'.csv'"
        export delimited using "`fname'", replace

        restore
    }
}

log close
