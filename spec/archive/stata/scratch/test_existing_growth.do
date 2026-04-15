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
*  spec/test_existing_growth.do
*  ------------------------------------------------------------------
*  Check pre-existing growth_post variable
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

* Check if growth_post exists
capture confirm variable growth_post
if !_rc {
    di _n "=== PRE-EXISTING growth_post VARIABLE FOUND ==="
    sum growth_post, detail
    
    * Check how many unique values
    quietly tab growth_post
    di "Number of unique values: " r(r)
}

* Check what other growth variables exist
di _n "=== CHECKING FOR OTHER GROWTH VARIABLES ==="
ds *growth* *Growth*

* Now create our own growth and compare
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
    rename post_covid_growth_we new_growth_post
    tempfile new_growth
    save `new_growth'
restore

merge m:1 companyname using `new_growth', keep(match master)

* Compare if growth_post exists
capture confirm variable growth_post
if !_rc {
    di _n "=== COMPARING EXISTING vs NEW GROWTH ==="
    corr growth_post new_growth_post
    gen diff = growth_post - new_growth_post
    sum diff, detail
    
    * Check where they differ
    count if abs(diff) > 0.001 & !missing(diff)
    di "Number of observations with different values: " r(N)
}

* Test regression with pre-existing growth_post
capture confirm variable growth_post
if !_rc {
    di _n "=== REGRESSION WITH PRE-EXISTING growth_post ==="
    
    quietly sum growth_post, detail
    gen high_existing = (growth_post > r(p50)) if !missing(growth_post)
    
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
    
    gen var3_g = var3 * high_existing
    gen var5_g = var5 * high_existing
    gen var6_g = var6 * high_existing
    gen var7_g = var7 * high_existing
    
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_g var5_g = var6 var7 var6_g var7_g) ///
        var4 high_existing ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    di "Pre-existing growth_post - var5: " %9.3f _b[var5]
}