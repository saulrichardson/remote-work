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
*  spec/test_trace_difference.do
*  ------------------------------------------------------------------
*  Trace back to find where 6.126 came from
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* Replicate my original test that gave 6.126
*--------------------------------------------------------------------*
di _n "=== REPLICATING ORIGINAL TEST (6.126) ==="

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Original approach: using collapse for firm controls
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

* Original regression WITHOUT high_growth control
di _n "--- Version 1: WITHOUT high_growth control ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "WITHOUT control - var5: " %9.3f _b[var5]

* Now WITH high_growth control
di _n "--- Version 2: WITH high_growth control ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 high_growth ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "WITH control - var5: " %9.3f _b[var5]

*--------------------------------------------------------------------*
* Now test with growth_post variable name
*--------------------------------------------------------------------*
drop var3_highgrowth var5_highgrowth var6_highgrowth var7_highgrowth

* Recreate with different name
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
    keep companyname post_covid_growth_we
    rename post_covid_growth_we growth_post  // KEY DIFFERENCE: different name
    tempfile post_growth
    save `post_growth'
restore

drop high_growth
merge m:1 companyname using `post_growth', keep(match) nogen

quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

di _n "--- Version 3: With growth_post name and control ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "With growth_post name - var5: " %9.3f _b[var5]