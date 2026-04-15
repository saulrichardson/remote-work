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
* Scaling Composition Horse Race - Simple Version
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

* Merge composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match master) nogen

* Keep only observations with composition data
drop if missing(engineer_share_2019)

*-----------------------------------------------------------------------------*
* Create composition interactions
*-----------------------------------------------------------------------------*

* Create interactions with var3 and var5
gen var3_engineer = var3 * engineer_share_2019
gen var5_engineer = var5 * engineer_share_2019

gen var3_sales = var3 * sales_share_2019
gen var5_sales = var5 * sales_share_2019

gen var3_marketing = var3 * marketing_share_2019
gen var5_marketing = var5 * marketing_share_2019

gen var3_entry = var3 * level1_share_2019
gen var5_entry = var5 * level1_share_2019

*-----------------------------------------------------------------------------*
* Run horse race regressions
*-----------------------------------------------------------------------------*

* Baseline
reg growth_rate_we var3 var5 var4 i.firm_id i.yh, cluster(firm_id)
est store base

* Engineer
reg growth_rate_we var3 var5 var4 var3_engineer var5_engineer i.firm_id i.yh, cluster(firm_id)
est store engineer

* Sales
reg growth_rate_we var3 var5 var4 var3_sales var5_sales i.firm_id i.yh, cluster(firm_id)
est store sales

* Marketing
reg growth_rate_we var3 var5 var4 var3_marketing var5_marketing i.firm_id i.yh, cluster(firm_id)
est store marketing

* Entry level
reg growth_rate_we var3 var5 var4 var3_entry var5_entry i.firm_id i.yh, cluster(firm_id)
est store entry

*-----------------------------------------------------------------------------*
* Display results
*-----------------------------------------------------------------------------*

esttab base engineer sales marketing entry, ///
    keep(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry")

*-----------------------------------------------------------------------------*
* Export clean table
*-----------------------------------------------------------------------------*

esttab base engineer sales marketing entry using "$results/scaling_comp_horse_race_final.txt", ///
    replace ///
    keep(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry") ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer "Remote × Post × Engineer%" ///
              var5_engineer "Remote × Post × Startup × Engineer%" ///
              var3_sales "Remote × Post × Sales%" ///
              var5_sales "Remote × Post × Startup × Sales%" ///
              var3_marketing "Remote × Post × Marketing%" ///
              var5_marketing "Remote × Post × Startup × Marketing%" ///
              var3_entry "Remote × Post × Entry%" ///
              var5_entry "Remote × Post × Startup × Entry%") ///
    title("Scaling Composition Horse Race Results")

di "Results saved to: $results/scaling_comp_horse_race_final.txt"