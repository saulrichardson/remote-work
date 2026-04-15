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
*  spec/test_final_difference.do
*  ------------------------------------------------------------------
*  Final test to identify coefficient difference
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

di _n "=== TEST 1: MY ORIGINAL APPROACH (6.126) ==="
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* My approach: simple firm controls merge
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

* Growth calculation
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

gen var3_highgrowth = var3 * high_growth
gen var5_highgrowth = var5 * high_growth
gen var6_highgrowth = var6 * high_growth
gen var7_highgrowth = var7 * high_growth

di "Sample size: " _N

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "My approach - var5 coefficient: " %9.3f _b[var5]

di _n "=== TEST 2: HORSE RACE APPROACH (8.386) ==="
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Horse race approach: bysort before merge
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    bysort companyname_c: keep if _n == _N
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

* Growth with different variable name
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
    rename post_covid_growth_we growth_post
    tempfile post_growth
    save `post_growth'
restore

merge m:1 companyname using `post_growth', keep(match) nogen

quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

di "Sample size: " _N

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "Horse race approach - var5 coefficient: " %9.3f _b[var5]

di _n "=== SUMMARY ==="
di "The difference appears to be in:"
di "1. Variable naming (growth_post vs post_covid_growth_we)"
di "2. bysort vs collapse in firm_controls merge"
di "3. Inclusion of high_growth_post as control"