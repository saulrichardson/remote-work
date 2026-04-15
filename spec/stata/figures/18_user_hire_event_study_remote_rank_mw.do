*============================================================*
* Asset 18: user_hire_event_study_remote_rank_mw.png
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local asset_stem "18_user_hire_event_study_remote_rank_mw"

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

use "$clean_data/user_hire_event_panel_`panel_variant'.dta", clear

keep if inrange(event_time, -3, 3)

capture confirm variable dest_startup
if _rc {
    di as error "dest_startup missing; rebuild panel via src/py/build_remote_hire_event_panel.py"
    exit 198
}
capture confirm variable dest_large
if _rc {
    di as error "dest_large missing; rebuild panel via src/py/build_remote_hire_event_panel.py"
    exit 198
}

local tlist "-3 -2 0 1 2 3"

gen byte evt = event_time + 3
label define evtlbl 0 "-3" 1 "-2" 2 "-1" 3 "0" 4 "1" 5 "2" 6 "3", replace
label values evt evtlbl
fvset base 2 evt

local rhs "i.evt##i.dest_startup"

tempfile results_buffer
capture postclose handle
postfile handle str8 group int event_time str40 outcome str8 model double b lb ub using `results_buffer', replace

local outcomes "total_contributions_q100 total_contributions total_contributions_we"

foreach y of local outcomes {
    di as text "Estimating OLS hire event study for `y'"
    reghdfe `y' `rhs', absorb(user_id firm_id yh) vce(cluster user_id) noconstant

    foreach t of local tlist {
        local evt_value = `t' + 3

        lincom `evt_value'.evt
        local b_large = r(estimate)
        local se_large = r(se)
        local lb_large = `b_large' - 1.96 * `se_large'
        local ub_large = `b_large' + 1.96 * `se_large'
        post handle ("large") (`t') ("`y'") ("OLS") (`b_large') (`lb_large') (`ub_large')

        lincom `evt_value'.evt + `evt_value'.evt#1.dest_startup
        local b_startup = r(estimate)
        local se_startup = r(se)
        local lb_startup = `b_startup' - 1.96 * `se_startup'
        local ub_startup = `b_startup' + 1.96 * `se_startup'
        post handle ("startup") (`t') ("`y'") ("OLS") (`b_startup') (`lb_startup') (`ub_startup')
    }
}

postclose handle
use `results_buffer', clear

export delimited using "`result_dir'/ols_results.csv", replace delimiter(",") quote

di as result "Saved CSV: `result_dir'/ols_results.csv"
log close
