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
*  spec/test_final_isolation.do
*  ------------------------------------------------------------------
*  Final test to isolate the 6.126 vs 8.386 difference
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* Start fresh with exact horse race approach
*--------------------------------------------------------------------*
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
    tempfile growth_temp
    save `growth_temp'
restore

*--------------------------------------------------------------------*
* Test different scenarios
*--------------------------------------------------------------------*

* Scenario 1: Keep original name
preserve
    merge m:1 companyname using `growth_temp', keep(match) nogen
    
    quietly sum post_covid_growth_we, detail
    gen high_growth = (post_covid_growth_we > r(p50)) if !missing(post_covid_growth_we)
    
    gen var3_highgrowth = var3 * high_growth
    gen var5_highgrowth = var5 * high_growth
    gen var6_highgrowth = var6 * high_growth
    gen var7_highgrowth = var7 * high_growth
    
    di _n "=== SCENARIO 1: Original name (post_covid_growth_we) ==="
    
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
        var4 ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    di "Scenario 1 - var5: " %9.3f _b[var5]
restore

* Scenario 2: Rename to growth_post
preserve
    merge m:1 companyname using `growth_temp', keep(match) nogen
    rename post_covid_growth_we growth_post
    
    quietly sum growth_post, detail
    gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)
    
    gen var3_growth = var3 * high_growth_post
    gen var5_growth = var5 * high_growth_post
    gen var6_growth = var6 * high_growth_post
    gen var7_growth = var7 * high_growth_post
    
    di _n "=== SCENARIO 2: Renamed to growth_post ==="
    
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
        var4 high_growth_post ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    di "Scenario 2 - var5: " %9.3f _b[var5]
    
    * Also check e(sample)
    gen sample2 = e(sample)
    count if sample2 == 1
    local n2 = r(N)
restore

* Scenario 3: Check if it's about the merge
use "$processed_data/user_panel_`panel_variant'.dta", clear

* Direct calculation without firm controls first
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
    tempfile growth_first
    save `growth_first'
restore

merge m:1 companyname using `growth_first', keep(match) nogen

* Now add firm controls
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

quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

di _n "=== SCENARIO 3: Growth merge before firm controls ==="

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "Scenario 3 - var5: " %9.3f _b[var5]