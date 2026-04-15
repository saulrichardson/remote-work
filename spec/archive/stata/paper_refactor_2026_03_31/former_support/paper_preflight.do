* ----------------------------------------------------------------------
* spec/archive/stata/paper_refactor_2026_03_31/former_support/paper_preflight.do
* Former Stata package preflight for the active logic-owned paper lane.
* ----------------------------------------------------------------------

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
log using "$LOG_DIR/paper_preflight.log", replace text

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

capture which _gxtile
if _rc {
    di as error "Required egenmore helper '_gxtile' not found."
    di as error "Install once via:  ssc install egenmore, replace"
    exit 199
}

di as result "Active logic-owned paper lane Stata preflight passed."
log close
