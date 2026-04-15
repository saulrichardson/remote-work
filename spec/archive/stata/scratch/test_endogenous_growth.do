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
*  spec/test_endogenous_growth.do
*  ------------------------------------------------------------------
*  Simplified version to test just endogenous growth interaction
*  Based on user_productivity_expost_growth_loop.do
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

*--------------------------------------------------------------------*
* Get firm controls
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

*--------------------------------------------------------------------*
* Calculate POST-COVID growth (endogenous)
*--------------------------------------------------------------------*
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    
    gen yh = hofd(date)
    format yh %th
    
    * Drop June 2022 outliers
    drop if date == 22797
    
    collapse (last) total_employees date, by(companyname yh)
    
    gen byte covid = (yh >= 120)
    
    * Static growth measure
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    gen post_covid_growth = (total_employees1 - total_employees0) / total_employees0
    winsor2 post_covid_growth, cuts(1 99) suffix(_we)
    keep companyname post_covid_growth_we
    
    * Create binary indicator (above median)
    quietly sum post_covid_growth_we, detail
    gen high_growth = (post_covid_growth_we > r(p50)) if !missing(post_covid_growth_we)
    
    tempfile growth_data
    save `growth_data'
restore

*--------------------------------------------------------------------*
* Merge and create interactions
*--------------------------------------------------------------------*
merge m:1 companyname using `growth_data', keep(match) nogen

* Create interaction variables
gen var3_highgrowth = var3 * high_growth
gen var5_highgrowth = var5 * high_growth
gen var6_highgrowth = var6 * high_growth
gen var7_highgrowth = var7 * high_growth

*--------------------------------------------------------------------*
* Run regressions and display results
*--------------------------------------------------------------------*
di _n "=== ENDOGENOUS GROWTH SPECIFICATION ==="
di _n "--- OLS ---"
reghdfe total_contributions_q100 var3 var5 var3_highgrowth var5_highgrowth var4 high_growth, ///
    absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "--- IV (Version 1: Original) ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 high_growth ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Store results
local b3_v1 = _b[var3]
local b5_v1 = _b[var5] 
local b3_int_v1 = _b[var3_highgrowth]
local b5_int_v1 = _b[var5_highgrowth]

di _n "--- IV (Version 2: Without high_growth control) ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Display key coefficients
di _n "=== KEY RESULTS ==="
di "Remote × COVID (low growth): " _b[var3]
di "Remote × COVID × Startup (low growth): " _b[var5]
di "Remote × COVID × High Growth: " _b[var3_highgrowth]
di "Remote × COVID × Startup × High Growth: " _b[var5_highgrowth]

* Calculate combined effects
di _n "=== COMBINED EFFECTS (Version 2) ==="
di "Regular firms - low growth: " _b[var3]
di "Regular firms - high growth: " _b[var3] + _b[var3_highgrowth]
di "Startups - low growth: " _b[var3] + _b[var5]
di "Startups - high growth: " _b[var3] + _b[var5] + _b[var3_highgrowth] + _b[var5_highgrowth]

di _n "=== COMPARISON ==="
di "Version 1 - Startups low growth: " `b3_v1' + `b5_v1'
di "Version 1 - Startups high growth: " `b3_v1' + `b5_v1' + `b3_int_v1' + `b5_int_v1'
di "Version 2 - Startups low growth: " _b[var3] + _b[var5]
di "Version 2 - Startups high growth: " _b[var3] + _b[var5] + _b[var3_highgrowth] + _b[var5_highgrowth]