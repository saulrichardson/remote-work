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
*  spec/user_productivity_scaling_horse_race_6126.do
*  ------------------------------------------------------------------
*  Horse race specification that produces var5 = 6.126
*  Based on exact replication of test_trace_difference.do
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Use collapse for firm controls (as in test_trace_difference.do)
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

* Original growth calculation
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    gen yh = hofd(date)
    format yh %th
    drop if date == 22797
    collapse (last) total_employees date, by(companyname yh)
    gen byte covid = (yh >= 120)
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    gen post_covid_growth = (total_employees1 - total_employees0) / total_employees0
    winsor2 post_covid_growth, cuts(1 99) suffix(_we)
    quietly sum post_covid_growth_we, detail
    gen high_growth = (post_covid_growth_we > r(p50)) if !missing(post_covid_growth_we)
    keep companyname high_growth
    tempfile growth_data
    save `growth_data'
restore

merge m:1 companyname using `growth_data', keep(match) nogen

* Original interactions (without _post suffix)
gen var3_highgrowth = var3 * high_growth
gen var5_highgrowth = var5 * high_growth
gen var6_highgrowth = var6 * high_growth
gen var7_highgrowth = var7 * high_growth

* Regression WITHOUT high_growth control - this yields 6.126
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== RESULT: var5 coefficient = " %9.6f _b[var5] " ==="
di "This should be approximately 6.126241"