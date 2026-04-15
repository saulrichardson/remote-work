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
use "../data/processed/firm_panel.dta", clear
assert !missing(companyname)
assert !missing(yh)

gen companyname_lower = lower(companyname)
gen str12 yh_str = string(yh, "%th")
gen int yh_year = real(substr(yh_str, 1, 4))
gen byte yh_half = real(substr(yh_str, 6, 1))
gen long yh_key = yh_year*2 + (yh_half == 2)
drop yh_str yh_year yh_half

duplicates report companyname_lower yh_key

exit
