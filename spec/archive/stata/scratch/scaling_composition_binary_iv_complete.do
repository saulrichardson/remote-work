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
* Binary Composition Analysis - Complete OLS and IV Version
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
* Create BINARY composition variables
*-----------------------------------------------------------------------------*

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

*-----------------------------------------------------------------------------*
* Create ALL interactions (OLS and IV)
*-----------------------------------------------------------------------------*

* OLS interactions
foreach role in engineer sales finance marketing admin operations scientist {
    gen var3_`role'_high = var3 * `role'_share_2019_high
    gen var5_`role'_high = var5 * `role'_share_2019_high
}

foreach level in level1 level2 level3 level4 {
    gen var3_`level'_high = var3 * `level'_share_2019_high
    gen var5_`level'_high = var5 * `level'_share_2019_high
}

* IV interactions
foreach role in engineer sales finance marketing admin operations scientist {
    gen var6_`role'_high = var6 * `role'_share_2019_high
    gen var7_`role'_high = var7 * `role'_share_2019_high
}

foreach level in level1 level2 level3 level4 {
    gen var6_`level'_high = var6 * `level'_share_2019_high
    gen var7_`level'_high = var7 * `level'_share_2019_high
}

*-----------------------------------------------------------------------------*
* ROLE COMPOSITION - OLS AND IV
*-----------------------------------------------------------------------------*

tempname role_ols_results role_iv_results

* OLS Baseline
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `role_ols_results' = (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., ., .)

* IV Baseline
ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `role_iv_results' = (e(N), e(rkf), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., ., e(rkf))

* Each role - OLS then IV
foreach role in engineer sales finance marketing admin operations scientist {
    * OLS
    reghdfe growth_rate_we var3 var5 var4 var3_`role'_high var5_`role'_high, absorb(firm_id yh) vce(cluster firm_id)
    matrix `role_ols_results' = `role_ols_results' \ (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`role'_high], _se[var3_`role'_high], _b[var5_`role'_high], _se[var5_`role'_high], .)
    
    * IV
    ivreghdfe growth_rate_we (var3 var5 var3_`role'_high var5_`role'_high = var6 var7 var6_`role'_high var7_`role'_high) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    matrix `role_iv_results' = `role_iv_results' \ (e(N), e(rkf), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`role'_high], _se[var3_`role'_high], _b[var5_`role'_high], _se[var5_`role'_high], e(rkf))
}

* Export results
preserve
clear
svmat `role_ols_results'
rename (`role_ols_results'1-`role_ols_results'11) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5 fstat)
gen model = "OLS"
gen role = _n
tempfile ols_role
save `ols_role'

clear
svmat `role_iv_results'
rename (`role_iv_results'1-`role_iv_results'11) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5 fstat)
gen model = "IV"
gen role = _n
append using `ols_role'
export delimited using "$results/role_binary_ols_iv_results.csv", replace
restore

*-----------------------------------------------------------------------------*
* SENIORITY COMPOSITION - OLS AND IV
*-----------------------------------------------------------------------------*

tempname sen_ols_results sen_iv_results

* OLS Baseline
reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `sen_ols_results' = (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., ., .)

* IV Baseline
ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
matrix `sen_iv_results' = (e(N), e(rkf), _b[var3], _se[var3], _b[var5], _se[var5], ., ., ., ., e(rkf))

* Each seniority level - OLS then IV
foreach level in level1 level2 level3 level4 {
    * OLS
    reghdfe growth_rate_we var3 var5 var4 var3_`level'_high var5_`level'_high, absorb(firm_id yh) vce(cluster firm_id)
    matrix `sen_ols_results' = `sen_ols_results' \ (e(N), e(r2_a), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`level'_high], _se[var3_`level'_high], _b[var5_`level'_high], _se[var5_`level'_high], .)
    
    * IV
    ivreghdfe growth_rate_we (var3 var5 var3_`level'_high var5_`level'_high = var6 var7 var6_`level'_high var7_`level'_high) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    matrix `sen_iv_results' = `sen_iv_results' \ (e(N), e(rkf), _b[var3], _se[var3], _b[var5], _se[var5], _b[var3_`level'_high], _se[var3_`level'_high], _b[var5_`level'_high], _se[var5_`level'_high], e(rkf))
}

* Export results
preserve
clear
svmat `sen_ols_results'
rename (`sen_ols_results'1-`sen_ols_results'11) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5 fstat)
gen model = "OLS"
gen level = _n
tempfile ols_sen
save `ols_sen'

clear
svmat `sen_iv_results'
rename (`sen_iv_results'1-`sen_iv_results'11) (n r2 b_var3 se_var3 b_var5 se_var5 b_int3 se_int3 b_int5 se_int5 fstat)
gen model = "IV"
gen level = _n
append using `ols_sen'
export delimited using "$results/seniority_binary_ols_iv_results.csv", replace
restore

di "Binary OLS and IV analysis complete"