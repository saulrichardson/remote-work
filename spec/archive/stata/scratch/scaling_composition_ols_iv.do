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
* Scaling Composition Horse Race - OLS and IV
* Following standard specification with both reghdfe and ivreghdfe
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

* Keep only merged observations with composition data
keep if !missing(engineer_share_2019)

*-----------------------------------------------------------------------------*
* Check for WFH exposure variable for IV
*-----------------------------------------------------------------------------*

cap confirm variable wfh_exposure
if _rc {
    di as error "wfh_exposure variable not found - cannot run IV specifications"
    exit
}

*-----------------------------------------------------------------------------*
* Create all necessary variables
*-----------------------------------------------------------------------------*

* Ensure base variables exist
cap gen var3 = remote * covid
cap gen var4 = covid * startup  
cap gen var5 = remote * covid * startup
cap gen var6 = wfh_exposure * covid
cap gen var7 = wfh_exposure * covid * startup

* Center composition variables at their means
foreach var in engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

* Create interactions for OLS
gen var3_engineer = var3 * engineer_share_2019_c
gen var5_engineer = var5 * engineer_share_2019_c

gen var3_sales = var3 * sales_share_2019_c
gen var5_sales = var5 * sales_share_2019_c

gen var3_marketing = var3 * marketing_share_2019_c
gen var5_marketing = var5 * marketing_share_2019_c

gen var3_entry = var3 * level1_share_2019_c
gen var5_entry = var5 * level1_share_2019_c

* Create IV interactions
gen var6_engineer = var6 * engineer_share_2019_c
gen var7_engineer = var7 * engineer_share_2019_c

gen var6_sales = var6 * sales_share_2019_c
gen var7_sales = var7 * sales_share_2019_c

gen var6_marketing = var6 * marketing_share_2019_c
gen var7_marketing = var7 * marketing_share_2019_c

gen var6_entry = var6 * level1_share_2019_c
gen var7_entry = var7 * level1_share_2019_c

*-----------------------------------------------------------------------------*
* Run OLS specifications using reghdfe
*-----------------------------------------------------------------------------*

estimates clear

* OLS Baseline
eststo ols1: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"
estadd local comp "None"

* OLS with engineer composition
eststo ols2: reghdfe growth_rate_we var3 var5 var4 var3_engineer var5_engineer, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"
estadd local comp "Engineer"

* OLS with sales composition
eststo ols3: reghdfe growth_rate_we var3 var5 var4 var3_sales var5_sales, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"
estadd local comp "Sales"

* OLS with marketing composition
eststo ols4: reghdfe growth_rate_we var3 var5 var4 var3_marketing var5_marketing, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"
estadd local comp "Marketing"

* OLS with entry composition
eststo ols5: reghdfe growth_rate_we var3 var5 var4 var3_entry var5_entry, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"
estadd local comp "Entry"

*-----------------------------------------------------------------------------*
* Run IV specifications using ivreghdfe
*-----------------------------------------------------------------------------*

* IV Baseline
eststo iv1: ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "IV"
estadd local comp "None"

* IV with engineer composition
eststo iv2: ivreghdfe growth_rate_we ///
    (var3 var5 var3_engineer var5_engineer = var6 var7 var6_engineer var7_engineer) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "IV"
estadd local comp "Engineer"

* IV with sales composition
eststo iv3: ivreghdfe growth_rate_we ///
    (var3 var5 var3_sales var5_sales = var6 var7 var6_sales var7_sales) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "IV"
estadd local comp "Sales"

* IV with marketing composition
eststo iv4: ivreghdfe growth_rate_we ///
    (var3 var5 var3_marketing var5_marketing = var6 var7 var6_marketing var7_marketing) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "IV"
estadd local comp "Marketing"

* IV with entry composition
eststo iv5: ivreghdfe growth_rate_we ///
    (var3 var5 var3_entry var5_entry = var6 var7 var6_entry var7_entry) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "IV"
estadd local comp "Entry"

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* Combined OLS and IV table
esttab ols1 ols2 ols3 iv1 iv2 iv3 using "$results/scaling_composition_ols_iv.tex", ///
    replace booktabs fragment ///
    keep(var3 var5 var3_engineer var5_engineer var3_sales var5_sales) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(model comp N r2_a rkf, fmt(0 0 0 3 2) ///
          labels("Model" "Composition" "Observations" "Adj. R-sq" "KP F-stat")) ///
    mtitles("(1)" "(2)" "(3)" "(4)" "(5)" "(6)") ///
    mgroups("OLS" "IV", pattern(1 0 0 1 0 0) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span) ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer "Remote × Post × Engineer\%" ///
              var5_engineer "Remote × Post × Startup × Engineer\%" ///
              var3_sales "Remote × Post × Sales\%" ///
              var5_sales "Remote × Post × Startup × Sales\%") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Scaling and Composition: OLS vs IV Horse Race}" ///
            "\label{tab:scaling_comp_ols_iv}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{6}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\scriptsize" ///
             "\item \textit{Notes:} Columns 1-3 show OLS results, columns 4-6 show IV results. " ///
             "IV specifications instrument for remote work using pre-COVID WFH exposure. " ///
             "Composition variables are centered at their means. " ///
             "All specifications include firm and year-half fixed effects. " ///
             "Standard errors clustered at firm level. " ///
             "\end{tablenotes}" "\end{table}")

* Full results table (all compositions)
esttab ols* iv* using "$results/scaling_composition_full_ols_iv.txt", ///
    replace ///
    keep(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(model comp N r2_a rkf, fmt(0 0 0 3 2)) ///
    mtitles("OLS Base" "OLS Eng" "OLS Sales" "OLS Mkt" "OLS Entry" ///
            "IV Base" "IV Eng" "IV Sales" "IV Mkt" "IV Entry") ///
    nonotes addnotes("All models include firm and year-half fixed effects" ///
                     "Standard errors clustered at firm level" ///
                     "Composition variables centered at mean" ///
                     "IV uses WFH exposure as instrument")

di "Results saved to:"
di "- $results/scaling_composition_ols_iv.tex (main table)"
di "- $results/scaling_composition_full_ols_iv.txt (full results)"

* Test for weak instruments
di _n "Kleibergen-Paap F-statistics:"
di "Baseline IV: " e(rkf)
estimates restore iv2
di "Engineer IV: " e(rkf)
estimates restore iv3
di "Sales IV: " e(rkf)