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
* Scaling Regressions with Binary Composition Variables
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

* Merge binary composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019_binary.dta", keep(match) nogen

*-----------------------------------------------------------------------------*
* Run regressions with binary indicators
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline
eststo col1: reg growth_rate_we startup age rent hhi_1000 i.yh, robust

* Column 2: High engineer firms
eststo col2: reg growth_rate_we startup engineer_high_2019 c.startup#c.engineer_high_2019 ///
    age rent hhi_1000 i.yh, robust

* Column 3: High sales firms  
eststo col3: reg growth_rate_we startup sales_high_2019 c.startup#c.sales_high_2019 ///
    age rent hhi_1000 i.yh, robust

* Column 4: Tech-focused firms
eststo col4: reg growth_rate_we startup tech_focused_2019 c.startup#c.tech_focused_2019 ///
    age rent hhi_1000 i.yh, robust

* Column 5: Customer-focused firms
eststo col5: reg growth_rate_we startup customer_focused_2019 c.startup#c.customer_focused_2019 ///
    age rent hhi_1000 i.yh, robust

* Column 6: Top-heavy firms (high management)
eststo col6: reg growth_rate_we startup top_heavy_2019 c.startup#c.top_heavy_2019 ///
    age rent hhi_1000 i.yh, robust

* Column 7: Bottom-heavy firms (high entry level)
eststo col7: reg growth_rate_we startup bottom_heavy_2019 c.startup#c.bottom_heavy_2019 ///
    age rent hhi_1000 i.yh, robust

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* LaTeX table
esttab col* using "$results/scaling_composition_binary.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *_2019 *startup*) ///
    order(startup *_2019 *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "High Eng" "High Sales" "Tech Focus" "Customer" "Top Heavy" "Entry Heavy") ///
    label

* Text version
esttab col* using "$results/scaling_composition_binary.txt", ///
    replace ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *_2019 *startup*) ///
    order(startup *_2019 *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "High Eng" "High Sales" "Tech Focus" "Customer" "Top Heavy" "Entry Heavy") ///
    label

di "Results saved to: $results/scaling_composition_binary.tex"