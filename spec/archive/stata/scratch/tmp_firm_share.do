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

version 17.0
set more off

* load merged panel
do "../globals.do"
use "$processed_data/user_panel_precovid_akm.dta", clear

* keep only workers with AKM FE
keep if !missing(akm_pfe_norm_2013to19)

gen byte high_akm = akm_pfe_norm_2013to19 > 0

* ensure canonical controls exist (assuming earn run earlier)

* aggregate to firm-year share
collapse (mean) high_akm=high_akm (firstnm) var3 var5 var4 var6 var7 post_shock remote_startup, by(firm_id year)

do "../globals.do"

reghdfe high_akm var3 var5 var4, absorb(firm_id year) vce(cluster firm_id)

ivreghdfe high_akm (var3 var5 = var6 var7) var4, absorb(firm_id year) vce(cluster firm_id) savefirst

log close _all
