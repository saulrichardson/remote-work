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
* Final Clean Composition Tables
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

* Center composition variables
foreach var in engineer_share_2019 sales_share_2019 finance_share_2019 marketing_share_2019 admin_share_2019 operations_share_2019 scientist_share_2019 level1_share_2019 level2_share_2019 level3_share_2019 level4_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

* Create all interactions upfront
foreach role in engineer sales finance marketing admin operations scientist {
    gen var3_`role' = var3 * `role'_share_2019_c
    gen var5_`role' = var5 * `role'_share_2019_c
}

foreach level in level1 level2 level3 level4 {
    gen var3_`level' = var3 * `level'_share_2019_c
    gen var5_`level' = var5 * `level'_share_2019_c
}

*-----------------------------------------------------------------------------*
* ROLE COMPOSITION REGRESSIONS
*-----------------------------------------------------------------------------*

* Store results temporarily
tempname role_results

* Baseline
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `role_results' = (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., .)

* Each role
foreach role in engineer sales finance marketing admin operations scientist {
    reghdfe growth_rate_we var3 var5 var4 var3_`role' var5_`role', absorb(firm_id yh) vce(cluster firm_id)
    matrix `role_results' = `role_results' \ (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`role'], _se[var3_`role'], _b[var5_`role'], _se[var5_`role'])
}

* Export role results
preserve
clear
svmat `role_results'
rename (`role_results'1-`role_results'10) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5)
gen role = _n
export delimited using "$results/role_results.csv", replace
restore

*-----------------------------------------------------------------------------*
* SENIORITY COMPOSITION REGRESSIONS  
*-----------------------------------------------------------------------------*

tempname sen_results

* Baseline
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `sen_results' = (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., .)

* Each seniority level
foreach level in level1 level2 level3 level4 {
    reghdfe growth_rate_we var3 var5 var4 var3_`level' var5_`level', absorb(firm_id yh) vce(cluster firm_id)
    matrix `sen_results' = `sen_results' \ (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`level'], _se[var3_`level'], _b[var5_`level'], _se[var5_`level'])
}

* Export seniority results
preserve
clear
svmat `sen_results'
rename (`sen_results'1-`sen_results'10) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5)
gen level = _n
export delimited using "$results/seniority_results.csv", replace
restore

di "Results exported to CSV files for table creation"