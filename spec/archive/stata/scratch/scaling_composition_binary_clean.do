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
* Clean Composition Tables with BINARY indicators
*=============================================================================*

clear all
set more off

global results "results/raw"
global cleaned "results/cleaned"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Load and prepare data
*-----------------------------------------------------------------------------*

use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match master) nogen
keep if !missing(engineer_share_2019)

*-----------------------------------------------------------------------------*
* Create BINARY composition variables (above/below median)
*-----------------------------------------------------------------------------*

* Calculate medians and create binary indicators
foreach var in engineer_share_2019 sales_share_2019 finance_share_2019 marketing_share_2019 admin_share_2019 operations_share_2019 scientist_share_2019 {
    sum `var', detail
    local median = r(p50)
    gen `var'_high = (`var' > `median')
    label var `var'_high "Above median `var'"
}

foreach var in level1_share_2019 level2_share_2019 level3_share_2019 level4_share_2019 {
    sum `var', detail
    local median = r(p50)
    gen `var'_high = (`var' > `median')
    label var `var'_high "Above median `var'"
}

* Create binary interactions
foreach role in engineer sales finance marketing admin operations scientist {
    gen var3_`role'_high = var3 * `role'_share_2019_high
    gen var5_`role'_high = var5 * `role'_share_2019_high
}

foreach level in level1 level2 level3 level4 {
    gen var3_`level'_high = var3 * `level'_share_2019_high
    gen var5_`level'_high = var5 * `level'_share_2019_high
}

*-----------------------------------------------------------------------------*
* ROLE COMPOSITION REGRESSIONS (BINARY)
*-----------------------------------------------------------------------------*

* Store results
tempname role_results

* Baseline
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `role_results' = (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., .)

* Each role (binary)
foreach role in engineer sales finance marketing admin operations scientist {
    reghdfe growth_rate_we var3 var5 var4 var3_`role'_high var5_`role'_high, absorb(firm_id yh) vce(cluster firm_id)
    matrix `role_results' = `role_results' \ (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`role'_high], _se[var3_`role'_high], _b[var5_`role'_high], _se[var5_`role'_high])
}

* Export role results
preserve
clear
svmat `role_results'
rename (`role_results'1-`role_results'10) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5)
gen role = _n
export delimited using "$results/role_binary_results.csv", replace
restore

*-----------------------------------------------------------------------------*
* SENIORITY COMPOSITION REGRESSIONS (BINARY)
*-----------------------------------------------------------------------------*

tempname sen_results

* Baseline
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `sen_results' = (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., .)

* Each seniority level (binary)
foreach level in level1 level2 level3 level4 {
    reghdfe growth_rate_we var3 var5 var4 var3_`level'_high var5_`level'_high, absorb(firm_id yh) vce(cluster firm_id)
    matrix `sen_results' = `sen_results' \ (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`level'_high], _se[var3_`level'_high], _b[var5_`level'_high], _se[var5_`level'_high])
}

* Export seniority results
preserve
clear
svmat `sen_results'
rename (`sen_results'1-`sen_results'10) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5)
gen level = _n
export delimited using "$results/seniority_binary_results.csv", replace
restore

*-----------------------------------------------------------------------------*
* IV SPECIFICATIONS FOR KEY VARIABLES
*-----------------------------------------------------------------------------*

* Create IV binary interactions
gen var6_sales_high = var6 * sales_share_2019_high
gen var7_sales_high = var7 * sales_share_2019_high
gen var6_engineer_high = var6 * engineer_share_2019_high
gen var7_engineer_high = var7 * engineer_share_2019_high

estimates clear

* OLS Baseline
eststo ols_base: reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)

* OLS Engineer High
eststo ols_eng: reghdfe growth_rate_we var3 var5 var4 var3_engineer_high var5_engineer_high, absorb(firm_id yh) vce(cluster firm_id)

* OLS Sales High
eststo ols_sales: reghdfe growth_rate_we var3 var5 var4 var3_sales_high var5_sales_high, absorb(firm_id yh) vce(cluster firm_id)

* IV Baseline
eststo iv_base: ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)

* IV Engineer High
eststo iv_eng: ivreghdfe growth_rate_we (var3 var5 var3_engineer_high var5_engineer_high = var6 var7 var6_engineer_high var7_engineer_high) var4, absorb(firm_id yh) vce(cluster firm_id)

* IV Sales High
eststo iv_sales: ivreghdfe growth_rate_we (var3 var5 var3_sales_high var5_sales_high = var6 var7 var6_sales_high var7_sales_high) var4, absorb(firm_id yh) vce(cluster firm_id)

* Export OLS vs IV comparison
esttab ols_* iv_* using "$results/scaling_binary_ols_iv.csv", ///
    keep(var3 var5 var3_*_high var5_*_high) ///
    cells(b(fmt(3)) se(fmt(3))) ///
    stats(N r2_a rkf, fmt(0 3 2)) ///
    replace

di "Binary composition analysis complete"
di "Results saved to:"
di "- $results/role_binary_results.csv"
di "- $results/seniority_binary_results.csv"
di "- $results/scaling_binary_ols_iv.csv"