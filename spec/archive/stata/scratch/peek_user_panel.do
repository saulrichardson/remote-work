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

clear all
set more off
use "data/processed/user_panel_precovid.dta", clear
keep companyname yh firm_id user_id
count
bysort firm_id yh: keep if _n==1
keep in 1/10
export delimited using "tmp_user_panel_keys.csv", replace
log using "peek_user_panel.log", replace text
list in 1/10
log close
