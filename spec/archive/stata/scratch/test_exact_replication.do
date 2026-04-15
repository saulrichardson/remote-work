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
*  spec/test_exact_replication.do
*  ------------------------------------------------------------------
*  Exact replication of horse race specification 2
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Get firm controls (following horse race script exactly)
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    bysort companyname_c: keep if _n == _N
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

* Calculate POST-COVID growth (following horse race script exactly)
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
    rename post_covid_growth_we growth_post
    tempfile post_growth
    save `post_growth'
restore

merge m:1 companyname using `post_growth', keep(match) nogen

* Create binary growth indicator
quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

* Create interactions
gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

di _n "=== REPLICATING HORSE RACE SPECIFICATION 2 ==="
di "Sample size: " _N
tab high_growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== KEY COEFFICIENTS ==="
di "var3: " %9.3f _b[var3]
di "var5: " %9.3f _b[var5]
di "var3_growth: " %9.3f _b[var3_growth]
di "var5_growth: " %9.3f _b[var5_growth]

* Also try without bysort in firm controls merge
drop high_growth_post var3_growth var5_growth var6_growth var7_growth

preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_controls2
    save `firm_controls2'
restore

merge m:1 companyname_c using `firm_controls2', keep(match) nogen

* Re-create growth variables
merge m:1 companyname using `post_growth', keep(match) nogen

quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

di _n "=== VERSION 2: WITH COLLAPSE INSTEAD OF BYSORT ==="
tab high_growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== KEY COEFFICIENTS (Version 2) ==="
di "var3: " %9.3f _b[var3]
di "var5: " %9.3f _b[var5]
di "var3_growth: " %9.3f _b[var3_growth]
di "var5_growth: " %9.3f _b[var5_growth]