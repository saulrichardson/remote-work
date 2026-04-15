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
* Productivity Regressions with Pre-COVID Composition - Simple Version
* Following standard var3/var5/var4 specification from other files
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
* Create interaction variables
*-----------------------------------------------------------------------------*

* For each composition variable, create interactions with var3 and var5
local all_comp "engineer sales finance marketing admin operations scientist level1 level2 level3 level4"

foreach comp of local all_comp {
    gen var3_`comp' = var3 * `comp'_share_2019
    gen var5_`comp' = var5 * `comp'_share_2019
    gen var6_`comp' = var6 * `comp'_share_2019
    gen var7_`comp' = var7 * `comp'_share_2019
}

*-----------------------------------------------------------------------------*
* Run regressions following standard specification
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline (standard specification)
eststo col1: ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) cluster(user_id)

* Columns 2-8: Add role composition controls
local roles "engineer sales finance marketing admin operations scientist"
local i = 2
foreach comp of local roles {
    eststo col`i': ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_`comp' var5_`comp' = var6 var7 var6_`comp' var7_`comp') ///
        var4 `comp'_share_2019, ///
        absorb(firm_id#user_id yh) cluster(user_id)
    local i = `i' + 1
}

* Columns 9-12: Add seniority composition controls
local seniority "level1 level2 level3 level4"
foreach comp of local seniority {
    eststo col`i': ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_`comp' var5_`comp' = var6 var7 var6_`comp' var7_`comp') ///
        var4 `comp'_share_2019, ///
        absorb(firm_id#user_id yh) cluster(user_id)
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* Table focusing on key coefficients
esttab col* using "$results/productivity_composition_precovid_all.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_* *_share_2019) ///
    order(var3 var5 var3_* var5_*) ///
    stats(N widstat, fmt(0 2)) ///
    mtitles("Base" "Eng" "Sales" "Fin" "Mkt" "Admin" "Ops" "Sci" "L1" "L2" "L3" "L4") ///
    replace

di "Results saved to: $results/productivity_composition_precovid_all.txt"