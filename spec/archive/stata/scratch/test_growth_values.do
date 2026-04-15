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
*  spec/test_growth_values.do
*  ------------------------------------------------------------------
*  Check if growth variables have same values
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

* Create both growth variables
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
    
    * Create both versions
    winsor2 post_covid_growth, cuts(1 99) suffix(_we)
    gen growth_version1 = post_covid_growth_we
    gen growth_post = post_covid_growth_we  // Same calculation, different name
    
    * Check if they're identical
    di _n "=== CHECKING GROWTH VARIABLES ==="
    corr growth_version1 growth_post
    gen diff = growth_version1 - growth_post
    sum diff
    
    * Create binary indicators
    quietly sum growth_version1, detail
    gen high_v1 = (growth_version1 > r(p50)) if !missing(growth_version1)
    
    quietly sum growth_post, detail
    gen high_post = (growth_post > r(p50)) if !missing(growth_post)
    
    tab high_v1 high_post
    
    keep companyname growth_version1 growth_post high_v1 high_post
    tempfile growth_compare
    save `growth_compare'
restore

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen
merge m:1 companyname using `growth_compare', keep(match) nogen

* Check if there's already a variable called growth_post
capture confirm variable growth_post
if !_rc {
    di _n "WARNING: growth_post already exists in the data!"
    di "This might be causing the issue"
}

* Test with explicit new variables
gen my_growth = growth_version1
gen my_high = high_v1

gen var3_test = var3 * my_high
gen var5_test = var5 * my_high
gen var6_test = var6 * my_high
gen var7_test = var7 * my_high

di _n "=== REGRESSION WITH NEW VARIABLE NAMES ==="
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_test var5_test = var6 var7 var6_test var7_test) ///
    var4 my_high ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "New names - var5: " %9.3f _b[var5]