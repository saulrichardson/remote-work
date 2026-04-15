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
* Scaling Regressions with Pre-COVID Composition
* This script tests how 2019 workforce composition predicts COVID-period growth
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Load and merge data
*-----------------------------------------------------------------------------*

* Load firm panel
use "$processed_data/firm_panel.dta", clear

* Create lowercase company name for merging
gen companyname_lower = lower(companyname)

* Keep COVID period only
keep if covid == 1

* Merge with pre-COVID composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

* Check merge success
count
di "Firms in COVID period with composition data: " r(N)

*-----------------------------------------------------------------------------*
* Part 2: Run scaling regressions
*-----------------------------------------------------------------------------*

* Store results
estimates clear

* Column 1: Baseline
eststo col1: reg growth_rate_we startup age rent hhi_1000 i.yh, robust

* Columns 2-8: Individual roles
local roles "engineer_share_2019 sales_share_2019 finance_share_2019 marketing_share_2019 admin_share_2019 operations_share_2019 scientist_share_2019"
local i = 2
foreach var of local roles {
    eststo col`i': reg growth_rate_we startup `var' c.startup#c.`var' age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

* Columns 9-12: Seniority levels
local seniority "level1_share_2019 level2_share_2019 level3_share_2019 level4_share_2019"
local i = 9
foreach var of local seniority {
    eststo col`i': reg growth_rate_we startup `var' c.startup#c.`var' age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Part 3: Display results
*-----------------------------------------------------------------------------*

* Table 1: Role effects
esttab col1 col2 col3 col4 col5 col6 col7 col8 using "$results/scaling_precovid_roles.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *_share_2019 *startup*) ///
    order(startup *_share_2019 *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Engineer" "Sales" "Finance" "Marketing" "Admin" "Operations" "Scientist") ///
    replace

* Table 2: Seniority effects
esttab col1 col9 col10 col11 col12 using "$results/scaling_precovid_seniority.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup level*_share_2019 *startup*) ///
    order(startup level*_share_2019 *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Level 1" "Level 2" "Level 3" "Level 4") ///
    replace

di _n "Scaling regressions with pre-COVID composition complete"
di "Results saved to:"
di "  - $results/scaling_precovid_roles.txt"
di "  - $results/scaling_precovid_seniority.txt"