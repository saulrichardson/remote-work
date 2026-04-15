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

* Quick fix to run just the vacancy specification
clear all
set more off

* Set globals
global raw_data "data/raw"
global processed_data "data/processed"
global results "results/raw"

* Load the main panel
use "$processed_data/user_panel_precovid.dta", clear

* Import and merge vacancy data properly
preserve
import delimited "$processed_data/vacancy_measures_2020.csv", clear
rename companyname companyname_c
destring vacancy vacancy_per_size, replace force
tempfile vac_data
save `vac_data'
restore

* Create lowercase company name for matching
gen companyname_c = lower(companyname)
merge m:1 companyname_c using `vac_data', keep(1 3) nogen

* Check merge success
count if !missing(vacancy_per_size)
di "Observations with vacancy data: " r(N)

* Generate interaction terms
gen var3_vac = var3 * vacancy_per_size
gen var5_vac = var5 * vacancy_per_size  
gen var6_vac = var6 * vacancy_per_size
gen var7_vac = var7 * vacancy_per_size

* Run the vacancy IV specification
di _n "=== VACANCY IV SPECIFICATION ==="
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_vac var5_vac = var6 var7 var6_vac var7_vac) ///
    var4 vacancy_per_size ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Extract and display results
di _n "Vacancy IV Results:"
di "Remote × Post: " %9.3f _b[var3] " (" %6.3f _se[var3] ")"
di "Remote × Post × Startup: " %9.3f _b[var5] " (" %6.3f _se[var5] ")"
di "Remote × Post × Vacancy: " %9.3f _b[var3_vac] " (" %6.3f _se[var3_vac] ")"
di "Remote × Post × Startup × Vacancy: " %9.3f _b[var5_vac] " (" %6.3f _se[var5_vac] ")"
di "KP F-stat: " %9.2f e(rkf)
di "N: " e(N)

* Store p-values
local p3 = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
local p5 = 2*ttail(e(df_r), abs(_b[var5]/_se[var5]))
local p3_vac = 2*ttail(e(df_r), abs(_b[var3_vac]/_se[var3_vac]))
local p5_vac = 2*ttail(e(df_r), abs(_b[var5_vac]/_se[var5_vac]))

di _n "P-values:"
di "var3 p = " %6.4f `p3'
di "var5 p = " %6.4f `p5'
di "var3_vac p = " %6.4f `p3_vac'
di "var5_vac p = " %6.4f `p5_vac'