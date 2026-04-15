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
*  spec/test_baseline_comparison.do
*  ------------------------------------------------------------------
*  Test baseline and growth interaction following standard approach
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* 1. Load data exactly as in user_productivity.do
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear

di _n "=== DATA CHECK ==="
count
sum var3 var5 var6 var7 var4

*--------------------------------------------------------------------*
* 2. Run baseline regression (no growth interaction)
*--------------------------------------------------------------------*
di _n "=== BASELINE SPECIFICATION (matching user_productivity.do) ==="

* OLS
di _n "--- OLS ---"
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* IV
di _n "--- IV ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local base_b3 = _b[var3]
local base_b5 = _b[var5]

*--------------------------------------------------------------------*
* 3. Now add growth following the horse race approach
*--------------------------------------------------------------------*
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

* Check sample size
di _n "=== SAMPLE SIZE CHECK ==="
count
tab high_growth

* Create interactions
gen var3_growth = var3 * high_growth
gen var5_growth = var5 * high_growth
gen var6_growth = var6 * high_growth
gen var7_growth = var7 * high_growth

*--------------------------------------------------------------------*
* 4. Run growth interaction specification
*--------------------------------------------------------------------*
di _n "=== GROWTH INTERACTION SPECIFICATION ==="

* IV without high_growth control (matching horse race approach)
di _n "--- IV (matching horse race specification) ---"
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== RESULTS COMPARISON ==="
di "Baseline var5 coefficient: " `base_b5'
di "Growth interaction var5 coefficient: " _b[var5]
di "Difference: " _b[var5] - `base_b5'