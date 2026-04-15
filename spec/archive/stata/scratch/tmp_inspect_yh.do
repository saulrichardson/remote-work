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

use "../data/processed/firm_panel.dta", clear
format yh %21.0f
di "First few yh values (numeric):"
list yh in 1/5

di "String formatted:"
format yh %th
list yh in 1/5

capture confirm numeric variable yh
if _rc di "yh not numeric" else di "yh numeric"

exit
