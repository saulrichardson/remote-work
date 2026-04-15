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
* Productivity Regressions with Composition - Corrected Version
* Composition only enters through interactions with var3 and var5
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Load and merge data
*-----------------------------------------------------------------------------*

use "$processed_data/user_panel_precovid.dta", clear
gen companyname_lower = lower(companyname)

* Merge composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

*-----------------------------------------------------------------------------*
* Run IV regressions - composition only through interactions
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline (no composition)
eststo col1: ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) cluster(user_id)

* Columns 2-8: Add role composition interactions
local roles "engineer sales finance marketing admin operations scientist"
local i = 2
foreach comp of local roles {
    * Create interaction variables
    gen var3_`comp' = var3 * `comp'_share_2019
    gen var5_`comp' = var5 * `comp'_share_2019
    gen var6_`comp' = var6 * `comp'_share_2019
    gen var7_`comp' = var7 * `comp'_share_2019
    
    * Run IV with composition interactions only
    eststo col`i': ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_`comp' var5_`comp' = var6 var7 var6_`comp' var7_`comp') var4, ///
        absorb(firm_id#user_id yh) cluster(user_id)
    local i = `i' + 1
}

* Columns 9-12: Add seniority interactions
local seniority "level1 level2 level3 level4"
foreach comp of local seniority {
    * Create interaction variables (if not already created)
    cap gen var3_`comp' = var3 * `comp'_share_2019
    cap gen var5_`comp' = var5 * `comp'_share_2019
    cap gen var6_`comp' = var6 * `comp'_share_2019
    cap gen var7_`comp' = var7 * `comp'_share_2019
    
    * Run IV with composition interactions only
    eststo col`i': ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_`comp' var5_`comp' = var6 var7 var6_`comp' var7_`comp') var4, ///
        absorb(firm_id#user_id yh) cluster(user_id)
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* Main table
esttab col1 col2 col3 col5 col9 col10 using "$results/productivity_composition_correct.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_* var4) ///
    order(var3 var5 var3_* var5_* var4) ///
    stats(N r2_a F, fmt(0 3 2)) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry" "Mid/Senior") ///
    label

di "Results saved to: $results/productivity_composition_correct.tex"