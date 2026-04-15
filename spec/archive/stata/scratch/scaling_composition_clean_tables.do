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
* Clean Composition Tables - Separate for Roles and Seniority
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
foreach var in engineer_share_2019 sales_share_2019 finance_share_2019 marketing_share_2019 admin_share_2019 operations_share_2019 scientist_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

foreach var in level1_share_2019 level2_share_2019 level3_share_2019 level4_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

*-----------------------------------------------------------------------------*
* PART 1: ROLE COMPOSITION TABLE
*-----------------------------------------------------------------------------*

estimates clear

* Baseline
eststo role_base: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

* Each role interaction
foreach role in engineer sales finance marketing admin operations scientist {
    gen var3_`role' = var3 * `role'_share_2019_c
    gen var5_`role' = var5 * `role'_share_2019_c
    
    eststo role_`role': reghdfe growth_rate_we var3 var5 var4 var3_`role' var5_`role', ///
        absorb(firm_id yh) vce(cluster firm_id)
}

* Export role table
esttab role_* using "$cleaned/scaling_roles_ols.tex", ///
    replace booktabs fragment ///
    keep(var3 var5 var3_* var5_*) ///
    order(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2_a, fmt(0 3) labels("Observations" "Adj. R-squared")) ///
    mtitles("Baseline" "Engineer" "Sales" "Finance" "Marketing" "Admin" "Operations" "Scientist") ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer "Remote × Post × Role\%" ///
              var5_engineer "Remote × Post × Startup × Role\%" ///
              var3_sales "Remote × Post × Role\%" ///
              var5_sales "Remote × Post × Startup × Role\%" ///
              var3_finance "Remote × Post × Role\%" ///
              var5_finance "Remote × Post × Startup × Role\%" ///
              var3_marketing "Remote × Post × Role\%" ///
              var5_marketing "Remote × Post × Startup × Role\%" ///
              var3_admin "Remote × Post × Role\%" ///
              var5_admin "Remote × Post × Startup × Role\%" ///
              var3_operations "Remote × Post × Role\%" ///
              var5_operations "Remote × Post × Startup × Role\%" ///
              var3_scientist "Remote × Post × Role\%" ///
              var5_scientist "Remote × Post × Startup × Role\%") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Remote Work Effects by Role Composition}" ///
            "\label{tab:scaling_roles}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{8}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\scriptsize" ///
             "\item \textit{Notes:} Each column adds interactions with a specific role's share of the workforce. " ///
             "Role shares are measured pre-COVID (2019) and centered at their means. " ///
             "All specifications include firm and year-half fixed effects. " ///
             "Standard errors clustered at firm level. " ///
             "\end{tablenotes}" "\end{table}")

*-----------------------------------------------------------------------------*
* PART 2: SENIORITY COMPOSITION TABLE
*-----------------------------------------------------------------------------*

estimates clear

* Baseline
eststo sen_base: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

* Each seniority level interaction
foreach level in level1 level2 level3 level4 {
    gen var3_`level' = var3 * `level'_share_2019_c
    gen var5_`level' = var5 * `level'_share_2019_c
    
    eststo sen_`level': reghdfe growth_rate_we var3 var5 var4 var3_`level' var5_`level', ///
        absorb(firm_id yh) vce(cluster firm_id)
}

* Export seniority table
esttab sen_* using "$cleaned/scaling_seniority_ols.tex", ///
    replace booktabs fragment ///
    keep(var3 var5 var3_* var5_*) ///
    order(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2_a, fmt(0 3) labels("Observations" "Adj. R-squared")) ///
    mtitles("Baseline" "Entry Level" "Mid/Senior" "Manager" "Director+") ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_level1 "Remote × Post × Seniority\%" ///
              var5_level1 "Remote × Post × Startup × Seniority\%" ///
              var3_level2 "Remote × Post × Seniority\%" ///
              var5_level2 "Remote × Post × Startup × Seniority\%" ///
              var3_level3 "Remote × Post × Seniority\%" ///
              var5_level3 "Remote × Post × Startup × Seniority\%" ///
              var3_level4 "Remote × Post × Seniority\%" ///
              var5_level4 "Remote × Post × Startup × Seniority\%") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Remote Work Effects by Seniority Composition}" ///
            "\label{tab:scaling_seniority}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{5}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\scriptsize" ///
             "\item \textit{Notes:} Each column adds interactions with a specific seniority level's share. " ///
             "Level 1 = Entry, Level 2 = Mid/Senior IC, Level 3 = Manager, Level 4 = Director+. " ///
             "Seniority shares are measured pre-COVID (2019) and centered at their means. " ///
             "All specifications include firm and year-half fixed effects. " ///
             "\end{tablenotes}" "\end{table}")

*-----------------------------------------------------------------------------*
* PART 3: IV SPECIFICATIONS (KEY ONES)
*-----------------------------------------------------------------------------*

* Create IV interactions for key variables
gen var6_sales = var6 * sales_share_2019_c
gen var7_sales = var7 * sales_share_2019_c
gen var6_engineer = var6 * engineer_share_2019_c  
gen var7_engineer = var7 * engineer_share_2019_c

estimates clear

* IV Baseline
eststo iv_base: ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

* IV Engineer
eststo iv_eng: ivreghdfe growth_rate_we ///
    (var3 var5 var3_engineer var5_engineer = var6 var7 var6_engineer var7_engineer) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

* IV Sales
eststo iv_sales: ivreghdfe growth_rate_we ///
    (var3 var5 var3_sales var5_sales = var6 var7 var6_sales var7_sales) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

* Export IV comparison
esttab role_base role_engineer role_sales iv_base iv_eng iv_sales ///
    using "$cleaned/scaling_ols_iv_comparison.tex", ///
    replace booktabs fragment ///
    keep(var3 var5 var3_engineer var5_engineer var3_sales var5_sales) ///
    order(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2_a rkf, fmt(0 3 2) labels("Observations" "Adj. R-sq" "KP F-stat")) ///
    mtitles("OLS Base" "OLS Eng" "OLS Sales" "IV Base" "IV Eng" "IV Sales") ///
    mgroups("OLS (reghdfe)" "IV (ivreghdfe)", pattern(1 0 0 1 0 0) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span)

di "Tables created:"
di "- $cleaned/scaling_roles_ols.tex"
di "- $cleaned/scaling_seniority_ols.tex"  
di "- $cleaned/scaling_ols_iv_comparison.tex"