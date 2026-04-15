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
* Scaling Regressions with Pre-COVID Composition - Simple Version
* Following standard specification from other files
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Load and merge data
*-----------------------------------------------------------------------------*

use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

* Keep COVID period
keep if covid == 1

* Merge composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

*-----------------------------------------------------------------------------*
* Run regressions following standard specification
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline (standard specification)
eststo col1: reg growth_rate_we startup age rent hhi_1000 i.yh, robust

* Columns 2-8: Add each role composition one at a time
local roles "engineer sales finance marketing admin operations scientist"
local i = 2
foreach var of local roles {
    eststo col`i': reg growth_rate_we startup `var'_share_2019 c.startup#c.`var'_share_2019 ///
        age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

* Columns 9-12: Add each seniority level one at a time  
local seniority "level1 level2 level3 level4"
foreach var of local seniority {
    eststo col`i': reg growth_rate_we startup `var'_share_2019 c.startup#c.`var'_share_2019 ///
        age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* Table with all columns
esttab col* using "$results/scaling_composition_precovid_all.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *_share_2019 *startup*) ///
    order(startup *_share_2019 *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Base" "Eng" "Sales" "Fin" "Mkt" "Admin" "Ops" "Sci" "L1" "L2" "L3" "L4") ///
    replace

di "Results saved to: $results/scaling_composition_precovid_all.txt"