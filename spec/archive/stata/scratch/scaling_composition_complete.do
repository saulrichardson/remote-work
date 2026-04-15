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
* Scaling Composition Horse Race - Complete OLS and IV
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

* Keep only merged observations
keep if !missing(engineer_share_2019)

*-----------------------------------------------------------------------------*
* Check and create necessary variables
*-----------------------------------------------------------------------------*

* Check if var6 and var7 exist (IV instruments)
cap confirm variable var6
if _rc {
    di "var6 not found - checking for alternative instrument construction"
    
    * Check for WFH exposure or other instrument
    cap confirm variable wfh_exposure_2019
    if !_rc {
        gen var6 = wfh_exposure_2019 * covid
        gen var7 = wfh_exposure_2019 * covid * startup
        di "Created var6 and var7 using wfh_exposure_2019"
    }
    else {
        * Try another approach - use pre-COVID remote share as instrument
        cap confirm variable remote_share_2019
        if !_rc {
            gen var6 = remote_share_2019 * covid
            gen var7 = remote_share_2019 * covid * startup
            di "Created var6 and var7 using remote_share_2019"
        }
        else {
            di as error "No suitable instrument found - will run OLS only"
            local iv_available = 0
        }
    }
}
else {
    di "var6 and var7 already exist"
    local iv_available = 1
}

*-----------------------------------------------------------------------------*
* Create composition interactions
*-----------------------------------------------------------------------------*

* Center composition variables
foreach var in engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

* OLS interactions
gen var3_engineer = var3 * engineer_share_2019_c
gen var5_engineer = var5 * engineer_share_2019_c

gen var3_sales = var3 * sales_share_2019_c
gen var5_sales = var5 * sales_share_2019_c

gen var3_marketing = var3 * marketing_share_2019_c
gen var5_marketing = var5 * marketing_share_2019_c

gen var3_entry = var3 * level1_share_2019_c
gen var5_entry = var5 * level1_share_2019_c

* IV interactions (if instruments available)
if "`iv_available'" == "1" {
    gen var6_engineer = var6 * engineer_share_2019_c
    gen var7_engineer = var7 * engineer_share_2019_c

    gen var6_sales = var6 * sales_share_2019_c
    gen var7_sales = var7 * sales_share_2019_c

    gen var6_marketing = var6 * marketing_share_2019_c
    gen var7_marketing = var7 * marketing_share_2019_c

    gen var6_entry = var6 * level1_share_2019_c
    gen var7_entry = var7 * level1_share_2019_c
}

*-----------------------------------------------------------------------------*
* Run OLS regressions
*-----------------------------------------------------------------------------*

estimates clear

* Baseline OLS
eststo ols_base: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"

* OLS with composition interactions
eststo ols_eng: reghdfe growth_rate_we var3 var5 var4 var3_engineer var5_engineer, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"

eststo ols_sales: reghdfe growth_rate_we var3 var5 var4 var3_sales var5_sales, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"

eststo ols_mkt: reghdfe growth_rate_we var3 var5 var4 var3_marketing var5_marketing, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"

eststo ols_entry: reghdfe growth_rate_we var3 var5 var4 var3_entry var5_entry, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"

*-----------------------------------------------------------------------------*
* Run IV regressions (if instruments available)
*-----------------------------------------------------------------------------*

if "`iv_available'" == "1" {
    * Baseline IV
    eststo iv_base: ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    estadd local model "IV"
    
    * Save F-stat
    estadd scalar fstat = e(rkf)

    * IV with composition interactions
    eststo iv_eng: ivreghdfe growth_rate_we ///
        (var3 var5 var3_engineer var5_engineer = var6 var7 var6_engineer var7_engineer) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    estadd local model "IV"
    estadd scalar fstat = e(rkf)

    eststo iv_sales: ivreghdfe growth_rate_we ///
        (var3 var5 var3_sales var5_sales = var6 var7 var6_sales var7_sales) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    estadd local model "IV"
    estadd scalar fstat = e(rkf)
}

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* OLS results table
esttab ols_* using "$results/scaling_composition_ols_final.tex", ///
    replace booktabs fragment ///
    keep(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2_a, fmt(0 3) labels("Observations" "Adj. R-squared")) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry") ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer "Remote × Post × Engineer\%" ///
              var5_engineer "Remote × Post × Startup × Engineer\%" ///
              var3_sales "Remote × Post × Sales\%" ///
              var5_sales "Remote × Post × Startup × Sales\%" ///
              var3_marketing "Remote × Post × Marketing\%" ///
              var5_marketing "Remote × Post × Startup × Marketing\%" ///
              var3_entry "Remote × Post × Entry\%" ///
              var5_entry "Remote × Post × Startup × Entry\%")

* Combined results if IV available
if "`iv_available'" == "1" {
    esttab ols_base ols_eng ols_sales iv_base iv_eng iv_sales ///
        using "$results/scaling_composition_combined.tex", ///
        replace booktabs fragment ///
        keep(var3 var5 var3_engineer var5_engineer var3_sales var5_sales) ///
        b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
        stats(model N r2_a fstat, fmt(0 0 3 2) ///
              labels("Model" "Observations" "Adj. R-sq" "KP F-stat")) ///
        mtitles("(1)" "(2)" "(3)" "(4)" "(5)" "(6)") ///
        mgroups("OLS" "IV", pattern(1 0 0 1 0 0))
}

* Summary statistics
sum engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019

di "Analysis complete. Check results in: $results/"