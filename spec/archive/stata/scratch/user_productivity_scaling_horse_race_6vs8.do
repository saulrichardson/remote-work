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
*  spec/user_productivity_scaling_horse_race_6vs8.do
*  ------------------------------------------------------------------
*  Compare 6.126 vs 8.386 coefficients
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Merge firm controls
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    collapse (last) rent hhi_1000, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

* Create growth measures
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

* Create interactions
gen var3_highgrowth = var3 * high_growth
gen var5_highgrowth = var5 * high_growth
gen var6_highgrowth = var6 * high_growth
gen var7_highgrowth = var7 * high_growth

* Specification 1: WITHOUT high_growth control (yields 6.126)
eststo clear
eststo spec1: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Store spec1 results
local var5_coef_spec1 = _b[var5]
local var5_se_spec1 = _se[var5]
local N_spec1 = e(N)

* Specification 2: WITH high_growth control (yields 8.386)
* First rename high_growth
rename high_growth high_growth_post

* Then create new interactions with _post suffix
gen var3_post = var3 * high_growth_post
gen var5_post = var5 * high_growth_post
gen var6_post = var6 * high_growth_post
gen var7_post = var7 * high_growth_post

eststo spec2: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_post var5_post = var6 var7 var6_post var7_post) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Store spec2 results
local var5_coef_spec2 = _b[var5]
local var5_se_spec2 = _se[var5]
local N_spec2 = e(N)

* Export results to CSV
esttab spec1 spec2 using "$results/scaling_horse_race_6vs8.csv", ///
    replace ///
    cells(b(fmt(6)) se(fmt(6))) ///
    keep(var3 var5 var3_highgrowth var5_highgrowth var3_post var5_post var4 high_growth_post) ///
    stats(N r2_a, fmt(0 4)) ///
    plain

* Create a summary CSV with the key coefficients
file open summary using "$results/horse_race_comparison_summary.csv", write replace
file write summary "specification,var5_coef,var5_se,N" _n
file write summary "without_control," %9.6f (`var5_coef_spec1') "," %9.6f (`var5_se_spec1') "," (`N_spec1') _n
file write summary "with_control," %9.6f (`var5_coef_spec2') "," %9.6f (`var5_se_spec2') "," (`N_spec2') _n
file close summary

di _n "=== RESULTS EXPORTED ==="
di "Main results: $results/scaling_horse_race_6vs8.csv"
di "Summary: $results/horse_race_comparison_summary.csv"