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

capture confirm file "$processed_data/user_panel_precovid.dta"
if _rc {
    global processed_data "data/processed"
    global base_results "results"
}
else {
    global processed_data "$processed_data"
    global base_results "$base_results"
}

use "$processed_data/user_panel_precovid.dta", clear

gen companyname_c = lower(companyname)

preserve
    use "$base_results/raw/composition_precovid_2019.dta", clear
    keep companyname_lower engineer_share_2019
    rename companyname_lower companyname_c
    tempfile comp
    save `comp'
restore

merge m:1 companyname_c using `comp', keep(match master)
keep if _merge == 3

drop _merge

xtile eng_tercile = engineer_share_2019, nq(3)

gen high_eng = (eng_tercile == 3)

gen low_eng = (eng_tercile <= 2)

keep if !missing(var3, var4, var5, var6, var7, high_eng)

// interactions

gen var3_high = var3 * high_eng

gen var3_low  = var3 * low_eng

gen var5_high = var5 * high_eng

gen var5_low  = var5 * low_eng

gen var6_high = var6 * high_eng

gen var6_low  = var6 * low_eng

gen var7_high = var7 * high_eng

gen var7_low  = var7 * low_eng

ivreghdfe total_contributions_q100 ///
    (var3_high var3_low var5_high var5_low = ///
        var6_high var6_low var7_high var7_low) ///
    var4, absorb(user_id firm_id yh) vce(cluster user_id) savefirst

matrix list e(first)

