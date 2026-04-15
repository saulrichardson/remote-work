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
*  spec/test_interaction_creation.do
*  ------------------------------------------------------------------
*  Test if interaction variable names matter
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    bysort companyname_c: keep if _n == _N
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

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

*--------------------------------------------------------------------*
* Test 1: My variable names
*--------------------------------------------------------------------*
di _n "=== TEST 1: MY VARIABLE NAMES ==="

gen var3_highgrowth = var3 * high_growth_post
gen var5_highgrowth = var5 * high_growth_post
gen var6_highgrowth = var6 * high_growth_post
gen var7_highgrowth = var7 * high_growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "My names - var5: " %9.3f _b[var5]
local my_b5 = _b[var5]

drop var3_highgrowth var5_highgrowth var6_highgrowth var7_highgrowth

*--------------------------------------------------------------------*
* Test 2: Horse race variable names
*--------------------------------------------------------------------*
di _n "=== TEST 2: HORSE RACE VARIABLE NAMES ==="

gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "Horse race names - var5: " %9.3f _b[var5]
local hr_b5 = _b[var5]

di _n "Difference: " %9.3f `hr_b5' - `my_b5'

*--------------------------------------------------------------------*
* Check if interactions are identical
*--------------------------------------------------------------------*
di _n "=== CHECKING IF INTERACTIONS ARE IDENTICAL ==="
corr var3_highgrowth var3_growth
corr var5_highgrowth var5_growth

gen diff3 = var3_highgrowth - var3_growth
gen diff5 = var5_highgrowth - var5_growth
sum diff3 diff5

*--------------------------------------------------------------------*
* Test 3: Check sample differences after regression
*--------------------------------------------------------------------*
di _n "=== SAMPLE CHECK ==="
di "Observations in regression: " e(N)
di "Clusters: " e(N_clust)

* Save estimation sample
gen in_sample = e(sample)
tab in_sample