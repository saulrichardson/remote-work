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

*====================================================================*
*  Test simplified version
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

* Load data and create simple test
use "$processed_data/user_panel_`panel_variant'.dta", clear

* Just test with baseline specification
di "Testing baseline specification"

* Simple regression
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)

di "Baseline OLS completed"
di "var3 coefficient: " _b[var3]
di "var5 coefficient: " _b[var5]

* IV regression
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)

di "Baseline IV completed"
di "var3 coefficient: " _b[var3]
di "var5 coefficient: " _b[var5]
di "First-stage F: " e(rkf)