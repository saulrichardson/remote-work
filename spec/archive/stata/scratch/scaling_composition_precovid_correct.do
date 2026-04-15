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
* Scaling Regressions with Pre-COVID Composition - Corrected Version
* Composition only enters through interactions with var3 and var5
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

* Create the standard variables
gen var3 = remote * covid
gen var4 = covid * startup  
gen var5 = remote * covid * startup

*-----------------------------------------------------------------------------*
* Run regressions - composition only through interactions
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline (no composition)
eststo col1: reg growth_rate_we var3 var5 startup age rent hhi_1000 i.yh, robust

* Columns 2-8: Add composition interactions for each role
local roles "engineer sales finance marketing admin operations scientist"
local i = 2
foreach var of local roles {
    * Create interaction variables
    gen var3_`var' = var3 * `var'_share_2019
    gen var5_`var' = var5 * `var'_share_2019
    
    * Run regression with interactions only (no standalone composition)
    eststo col`i': reg growth_rate_we var3 var5 var3_`var' var5_`var' ///
        startup age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

* Columns 9-12: Add seniority interactions
local seniority "level1 level2 level3 level4"
foreach var of local seniority {
    * Create interaction variables
    gen var3_`var' = var3 * `var'_share_2019
    gen var5_`var' = var5 * `var'_share_2019
    
    * Run regression with interactions only
    eststo col`i': reg growth_rate_we var3 var5 var3_`var' var5_`var' ///
        startup age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* LaTeX table
esttab col1 col2 col3 col5 col9 col10 using "$results/scaling_composition_correct.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_* startup) ///
    order(var3 var5 var3_* var5_* startup) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry" "Mid/Senior") ///
    label

* Full results
esttab col* using "$results/scaling_composition_correct_all.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_* startup) ///
    order(var3 var5 var3_* var5_* startup) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Base" "Eng" "Sales" "Fin" "Mkt" "Admin" "Ops" "Sci" "L1" "L2" "L3" "L4") ///
    replace

di "Results saved to: $results/scaling_composition_correct.tex"