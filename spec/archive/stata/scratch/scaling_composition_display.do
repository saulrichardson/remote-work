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
* Quick display of composition horse race results
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match master) nogen
keep if !missing(engineer_share_2019)

* Center composition variables
foreach var in engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

* Create interactions
gen var3_engineer = var3 * engineer_share_2019_c
gen var5_engineer = var5 * engineer_share_2019_c
gen var3_sales = var3 * sales_share_2019_c
gen var5_sales = var5 * sales_share_2019_c

* Run key regressions and display
di _n "=== COMPOSITION HORSE RACE RESULTS ===" _n

di "1. BASELINE (no composition):"
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)

di _n "2. WITH ENGINEER COMPOSITION:"
reghdfe growth_rate_we var3 var5 var4 var3_engineer var5_engineer, absorb(firm_id yh) vce(cluster firm_id)

di _n "3. WITH SALES COMPOSITION:"
reghdfe growth_rate_we var3 var5 var4 var3_sales var5_sales, absorb(firm_id yh) vce(cluster firm_id)

* Try IV if var6/var7 exist
cap confirm variable var6
if !_rc {
    di _n "4. IV BASELINE:"
    ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
    di "KP F-stat = " e(rkf)
    
    * Create IV interactions
    gen var6_sales = var6 * sales_share_2019_c
    gen var7_sales = var7 * sales_share_2019_c
    
    di _n "5. IV WITH SALES COMPOSITION:"
    ivreghdfe growth_rate_we (var3 var5 var3_sales var5_sales = var6 var7 var6_sales var7_sales) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    di "KP F-stat = " e(rkf)
}