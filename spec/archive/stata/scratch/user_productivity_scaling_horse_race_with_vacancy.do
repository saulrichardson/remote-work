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

*=============================================================================*
* Run the scaling horse race with vacancy specification
*=============================================================================*

clear all
set more off

do "src/globals.do"

* Load user panel
use "$processed_data/user_panel_precovid.dta", clear

* Merge vacancy data
preserve
import delimited "$processed_data/vacancy_measures_2020.csv", clear stringcols(_all)
rename companyname companyname_c
destring vacancy vacancy_per_size, replace force
tempfile vac_data
save `vac_data'
restore

gen companyname_c = lower(companyname)
merge m:1 companyname_c using `vac_data', keep(1 3) nogen

* Check if we have vacancy data
count if !missing(vacancy_per_size)
di "Observations with vacancy data: " r(N)

* Run the vacancy IV specification
di _n "=== VACANCY IV SPECIFICATION ==="

capture drop var3_vac var5_vac var6_vac var7_vac
gen var3_vac = var3 * vacancy_per_size
gen var5_vac = var5 * vacancy_per_size  
gen var6_vac = var6 * vacancy_per_size
gen var7_vac = var7 * vacancy_per_size

* Run IV with vacancy in first stage and as interaction
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_vac var5_vac = var6 var7 var6_vac var7_vac vacancy_per_size) ///
    var4 vacancy_per_size ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Display results
di _n "Vacancy IV Results:"
di "Remote × Post: " _b[var3] " (se=" _se[var3] ")"
di "Remote × Post × Startup: " _b[var5] " (se=" _se[var5] ")"
di "Remote × Post × Vacancy: " _b[var3_vac] " (se=" _se[var3_vac] ")"
di "Remote × Post × Startup × Vacancy: " _b[var5_vac] " (se=" _se[var5_vac] ")"
di "KP F-stat: " e(rkf)
di "N: " e(N)

* Export results
preserve
clear
set obs 1
gen specification = "vacancy_iv"
gen b3 = _b[var3]
gen se3 = _se[var3]
gen p3 = 2*ttail(e(df_r), abs(b3/se3))
gen b5 = _b[var5]
gen se5 = _se[var5]
gen p5 = 2*ttail(e(df_r), abs(b5/se5))
gen b3_vac = _b[var3_vac]
gen se3_vac = _se[var3_vac]
gen p3_vac = 2*ttail(e(df_r), abs(b3_vac/se3_vac))
gen b5_vac = _b[var5_vac]
gen se5_vac = _se[var5_vac]
gen p5_vac = 2*ttail(e(df_r), abs(b5_vac/se5_vac))
gen rkf = e(rkf)
gen nobs = e(N)
gen notes = "Vacancy per size as instrument and interaction"
export delimited "$results/raw/scaling_horse_race_precovid/vacancy_iv_results.csv", replace
restore