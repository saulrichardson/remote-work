********************************************************************************
** Build modal firm role from the raw worker-spell source.
********************************************************************************

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or src/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/build_firm_modal_role.log", replace text

capture confirm file "$raw_data/Scoop_workers_positions.csv"
if _rc {
    di as error "Missing required raw source: $raw_data/Scoop_workers_positions.csv"
    exit 601
}

import delimited "$raw_data/Scoop_workers_positions.csv", clear bindquote(strict) ///
    stringcols(_all)

gen start = date(start_date, "YMD")
gen end   = date(end_date, "YMD")
format start %td
format end   %td

local cutoff = date("2019-12-31", "YMD")
keep if start <= `cutoff' & (missing(end) | end >= `cutoff')

order companyname role_k7
bysort companyname role_k7 : gen _freq = _N
gsort companyname -_freq role_k7
bysort companyname : keep if _n == 1
keep companyname role_k7 _freq

save "$processed_data/modal_role_per_firm.dta", replace

log close
