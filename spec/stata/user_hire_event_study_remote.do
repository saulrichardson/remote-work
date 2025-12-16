*------------------------------------------------------------*
* user_hire_event_study_remote.do
* Event-study around hire date for remote hires: startups vs
* large firms. Uses precovid panel prepared by the Python
* helper `src/py/build_user_hire_event_panel.py`.
*------------------------------------------------------------*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_hire_event_study_remote_`panel_variant'

* Bootstrap paths
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

* Load prepped event-study panel (contains dest_startup/dest_large for hire firm)
use "$clean_data/user_hire_event_panel_`panel_variant'.dta", clear

* Window: keep baseline tau = -1 omitted; estimate pre (-3..-2) and post (0..3)
keep if inrange(event_time, -3, 3)

* Group flags: carry destination firm type (pre-hire rows may have remote=0)
cap confirm variable dest_startup
if _rc {
    di as error "dest_startup missing; rebuild panel via src/py/build_user_hire_event_panel.py"
    exit 198
}
cap confirm variable dest_large
if _rc {
    di as error "dest_large missing; rebuild panel via src/py/build_user_hire_event_panel.py"
    exit 198
}

* Only the supported window tau = -3..-2 and 0..3 is modeled; tau = -1 remains
* in the data as the omitted baseline for the event-time factor. Established firms are
* the reference group; startup effects come from interactions.
local tlist "-3 -2 0 1 2 3"

* Create a shifted event index to allow a positive base level (simplifies fvset)
gen byte evt = event_time + 3
label define evtlbl 0 "-3" 1 "-2" 2 "-1" 3 "0" 4 "1" 5 "2" 6 "3", replace
label values evt evtlbl
fvset base 2 evt   // base corresponds to event_time = -1

local rhs "i.evt##i.dest_startup"

local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle str8 group int event_time str40 outcome str8 model double b lb ub using `out', replace


local outcomes "total_contributions_q100 total_contributions total_contributions_we"

foreach y of local outcomes {
    di as text "→ OLS: `y'"
    reghdfe `y' `rhs', absorb(user_id firm_id yh) vce(cluster user_id) noconstant

    * Save regression-sample stats for the rank outcome (used in LaTeX table)
    if "`y'" == "total_contributions_q100" {
        preserve
            keep if e(sample)
            cap drop pre_mean
            tempvar pm
            bys dest_startup: egen N_group = count(total_contributions_q100)
            bys dest_startup: egen `pm' = mean(total_contributions_q100) if event_time==-1
            bys dest_startup: egen pre_mean = max(`pm')
            keep dest_startup N_group pre_mean
            duplicates drop dest_startup, force
            gen N_total = e(N)
            gen clusters = e(N_clust)
            export delimited using "`result_dir'/sample_stats.csv", replace
        restore
    }

    foreach t of local tlist {
        local v = `t' + 3   // evt value for this event_time

        * established firm (dest_startup=0): main effect for tau=t vs tau=-1
        lincom `v'.evt
        local bL  = r(estimate)
        local seL = r(se)
        local lbL = `bL' - 1.96*`seL'
        local ubL = `bL' + 1.96*`seL'
        post handle ("large") (`t') ("`y'") ("OLS") (`bL') (`lbL') (`ubL')

        * startup: main effect + interaction (startup minus established at tau=t)
        lincom `v'.evt + `v'.evt#1.dest_startup
        local bS  = r(estimate)
        local seS = r(se)
        local lbS = `bS' - 1.96*`seS'
        local ubS = `bS' + 1.96*`seS'
        post handle ("startup") (`t') ("`y'") ("OLS") (`bS') (`lbS') (`ubS')
    }
}

postclose handle
use `out', clear

export delimited using "`result_dir'/ols_results.csv", replace delimiter(",") quote
save "`result_dir'/ols_results.dta", replace

di as result "Saved CSV: `result_dir'/ols_results.csv"
log close
