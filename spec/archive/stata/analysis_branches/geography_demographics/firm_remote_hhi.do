*============================================================*
* firm_remote_hhi.do
* -----------------------------------------------------------*
* Cross-sectional test: do firms in more concentrated (higher *
* monopsony) HQ labor markets adopt remote work less?         *
*                                                             *
* Data: firm_panel (pre-COVID only), HQ monopsony HHI from    *
*       firm_hhi_hq.csv (built via CBSA×SOC HHIs).            *
* Model: remote_mean = α + β hhi_hq + controls + FE           *
*   Controls: log(size), age                                  *
*   FE: industry, CBSA (location_id)                          *
*   VCE: clustered by CBSA                                    *
*------------------------------------------------------------*
* Usage:                                                      *
*   stata-mp -b do spec/stata/firm_remote_hhi.do              *
*============================================================*

* 0) Paths
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/firm_remote_hhi.log", replace text

* 1) Load firm panel (pre-COVID only)
use "$clean_data/firm_panel.dta", clear
keep if covid == 0
gen companyname_lower = lower(companyname)

* 2) Bring in HQ monopsony HHI
tempfile hhi
import delimited using "$clean_data/firm_hhi_hq.csv", clear varnames(1) stringcols(_all)
keep companyname hhi_hq
gen companyname_lower = lower(companyname)
keep companyname_lower hhi_hq
duplicates drop companyname_lower, force
save `hhi'

use "$clean_data/firm_panel.dta", clear
keep if covid == 0
gen companyname_lower = lower(companyname)
merge m:1 companyname_lower using `hhi', keep(match) nogen

* 3) Collapse to firm-level means (remote, size, age) and identifiers
collapse ///
    (mean) remote employeecount age ///
    (first) industry_id location_id hhi_hq, ///
    by(companyname_lower)

rename remote        remote_mean
rename employeecount size_mean
rename age           age_mean
gen log_size = ln(size_mean + 1)

* 4) Estimation
* Bivariate
reghdfe remote_mean hhi_hq, vce(robust)

* With controls + FE + clustered SEs
reghdfe remote_mean hhi_hq log_size age_mean, ///
    absorb(industry_id location_id) ///
    vce(cluster location_id)

di as text "Effect per 1000 HHI points: " %9.4f (_b[hhi_hq]*1000)

log close
