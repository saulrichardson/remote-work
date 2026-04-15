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
* Prepare composition change variables for scaling and productivity tests
* Memory-efficient approach using tempfiles and aggregation
*=============================================================================*

clear all
set more off

do "src/globals.do"

*-----------------------------------------------------------------------------*
* PART 1: Calculate firm-level composition changes by SOC (role)
*-----------------------------------------------------------------------------*

* First, get pre and post COVID headcounts by SOC
tempfile pre_soc post_soc soc_changes

* Pre-COVID baseline (2019 H2)
use "$processed_data/firm_soc_panel_enriched.dta", clear
keep if yh == yh(2019,2)
collapse (sum) hc_pre=headcount, by(companyname soc4)
save `pre_soc'

* Post-COVID average (2020 H2 - 2021 H2)
use "$processed_data/firm_soc_panel_enriched.dta", clear
keep if inrange(yh, yh(2020,2), yh(2021,2))
collapse (mean) hc_post=headcount, by(companyname soc4)

* Merge and calculate % change
merge 1:1 companyname soc4 using `pre_soc'
gen pct_chg_soc = 100 * (hc_post - hc_pre) / hc_pre if hc_pre > 0
replace pct_chg_soc = 100 if hc_pre == 0 & hc_post > 0  // New roles
replace pct_chg_soc = -100 if hc_pre > 0 & hc_post == 0  // Eliminated roles

* Save SOC-level changes
keep companyname soc4 pct_chg_soc hc_pre hc_post
save `soc_changes'

* Create wide format for regression (top 10 SOCs)
* First identify top 10 SOCs by total employment
preserve
    collapse (sum) total_hc=hc_pre, by(soc4)
    gsort -total_hc
    keep if _n <= 10
    levelsof soc4, local(top_socs)
restore

* Create wide format with top SOCs
keep if inlist(soc4, `top_socs')
reshape wide pct_chg_soc hc_pre hc_post, i(companyname) j(soc4) string

* Fill missing with 0 (no employees in that SOC)
foreach v of varlist pct_chg_soc* {
    replace `v' = 0 if missing(`v')
}

save "$processed_data/firm_soc_composition_changes.dta", replace

*-----------------------------------------------------------------------------*
* PART 2: Calculate composition changes by seniority level
*-----------------------------------------------------------------------------*

* We need to get seniority data from the LinkedIn panel
* This requires processing the large file in chunks

tempfile seniority_changes

* Since we don't have direct seniority level breakdowns in the current data,
* we'll use the seniority_levels variable as a proxy
* This measures the number of distinct seniority levels in the firm

use "$processed_data/firm_panel.dta", clear
keep companyname yh seniority_levels total_employees

* Pre-COVID baseline
preserve
    keep if yh == yh(2019,2)
    rename seniority_levels sen_levels_pre
    rename total_employees emp_pre
    tempfile pre_sen
    save `pre_sen'
restore

* Post-COVID average
keep if inrange(yh, yh(2020,2), yh(2021,2))
collapse (mean) sen_levels_post=seniority_levels emp_post=total_employees, by(companyname)

* Merge and calculate changes
merge 1:1 companyname using `pre_sen', nogen

* Calculate seniority concentration change (simplified metric)
gen sen_concentration_chg = (sen_levels_post - sen_levels_pre) / sen_levels_pre * 100
gen emp_growth = (emp_post - emp_pre) / emp_pre * 100

save "$processed_data/firm_seniority_changes.dta", replace

*-----------------------------------------------------------------------------*
* PART 3: Merge composition changes with main panels
*-----------------------------------------------------------------------------*

* Add to firm panel
use "$processed_data/firm_panel.dta", clear
merge m:1 companyname using "$processed_data/firm_soc_composition_changes.dta", nogen keep(match master)
merge m:1 companyname using "$processed_data/firm_seniority_changes.dta", nogen keep(match master)
save "$processed_data/firm_panel_with_composition.dta", replace

* Add to user panel (memory efficient - process in chunks if needed)
use "$processed_data/user_panel_precovid.dta", clear
merge m:1 companyname using "$processed_data/firm_soc_composition_changes.dta", nogen keep(match master)
merge m:1 companyname using "$processed_data/firm_seniority_changes.dta", nogen keep(match master)
save "$processed_data/user_panel_with_composition.dta", replace

di "Composition change variables created successfully"