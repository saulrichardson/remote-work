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
*  spec/test_control_difference.do
*  ------------------------------------------------------------------
*  Test the effect of including high_growth as a control
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Get firm controls
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

* Calculate POST-COVID growth
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
    
    * Create binary indicator
    quietly sum post_covid_growth_we, detail
    gen high_growth = (post_covid_growth_we > r(p50)) if !missing(post_covid_growth_we)
    
    keep companyname post_covid_growth_we high_growth
    tempfile growth_data
    save `growth_data'
restore

merge m:1 companyname using `growth_data', keep(match) nogen

* Create interactions
gen var3_growth = var3 * high_growth
gen var5_growth = var5 * high_growth
gen var6_growth = var6 * high_growth
gen var7_growth = var7 * high_growth

di _n "=== COMPARISON OF SPECIFICATIONS ==="

* Version 1: WITHOUT high_growth control (my original test)
di _n "--- Version 1: WITHOUT high_growth control ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local v1_b3 = _b[var3]
local v1_b5 = _b[var5]
local v1_b3_int = _b[var3_growth]
local v1_b5_int = _b[var5_growth]
local v1_N = e(N)

* Version 2: WITH high_growth control (horse race approach)
di _n "--- Version 2: WITH high_growth control ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local v2_b3 = _b[var3]
local v2_b5 = _b[var5]
local v2_b3_int = _b[var3_growth]
local v2_b5_int = _b[var5_growth]
local v2_N = e(N)

di _n "=== COEFFICIENT COMPARISON ==="
di "var5 coefficient:"
di "  Version 1 (no control): " %9.3f `v1_b5'
di "  Version 2 (with control): " %9.3f `v2_b5'
di "  Difference: " %9.3f `v2_b5' - `v1_b5'

di _n "var5_growth coefficient:"
di "  Version 1 (no control): " %9.3f `v1_b5_int'
di "  Version 2 (with control): " %9.3f `v2_b5_int'

di _n "Sample size:"
di "  Version 1: " `v1_N'
di "  Version 2: " `v2_N'

di _n "Combined effects for startups:"
di "Low growth:"
di "  Version 1: " %9.3f `v1_b3' + `v1_b5'
di "  Version 2: " %9.3f `v2_b3' + `v2_b5'
di "High growth:"
di "  Version 1: " %9.3f `v1_b3' + `v1_b5' + `v1_b3_int' + `v1_b5_int'
di "  Version 2: " %9.3f `v2_b3' + `v2_b5' + `v2_b3_int' + `v2_b5_int'