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
* Scaling Regressions with Composition - Horse Race Style
* Following the same logic as scaling_horse_race specifications
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

*-----------------------------------------------------------------------------*
* Create interactions with composition
*-----------------------------------------------------------------------------*

* Define composition variables to test
local comp_vars "engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019 level2_share_2019"

* Create interactions for each composition variable
foreach comp of local comp_vars {
    gen var3_`comp' = var3 * `comp'
    gen var5_`comp' = var5 * `comp'
    gen var6_`comp' = var6 * `comp'
    gen var7_`comp' = var7 * `comp'
}

*-----------------------------------------------------------------------------*
* Run OLS regressions
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline (no composition)
eststo ols1: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"

* Columns 2-6: Add composition interactions one at a time
local i = 2
foreach comp of local comp_vars {
    eststo ols`i': reghdfe growth_rate_we ///
        var3 var5 var4 ///
        var3_`comp' var5_`comp', ///
        absorb(firm_id yh) vce(cluster firm_id)
    estadd local model "OLS"
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Run IV regressions
*-----------------------------------------------------------------------------*

* Column 7: Baseline IV
eststo iv1: ivreghdfe growth_rate_we ///
    (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "IV"

* Columns 8-12: IV with composition interactions
local i = 2
foreach comp of local comp_vars {
    eststo iv`i': ivreghdfe growth_rate_we ///
        (var3 var5 var3_`comp' var5_`comp' = ///
         var6 var7 var6_`comp' var7_`comp') var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    estadd local model "IV"
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* OLS results
esttab ols* using "$results/scaling_composition_ols_horse_race.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_*) ///
    order(var3 var5 var3_* var5_*) ///
    stats(model N r2_a rkf, fmt(0 0 3 2) ///
          labels("Model" "Observations" "Adj. R-sq" "KP F-stat")) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry" "Mid/Senior") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Scaling and Workforce Composition: OLS Horse Race}" ///
            "\label{tab:scaling_comp_ols}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{6}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\tiny" ///
             "\item \textit{Notes:} This table follows the horse race specification, adding composition interactions to var3 and var5. " ///
             "var3 = remote×covid, var5 = remote×covid×startup. " ///
             "Composition measured as pre-COVID (2019) percentage of workforce. " ///
             "All specifications include firm and year-half fixed effects. " ///
             "Standard errors clustered at firm level. " ///
             "\end{tablenotes}" "\end{table}")

* IV results
esttab iv* using "$results/scaling_composition_iv_horse_race.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_*) ///
    order(var3 var5 var3_* var5_*) ///
    stats(model N rkf, fmt(0 0 2) ///
          labels("Model" "Observations" "KP F-stat")) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry" "Mid/Senior") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Scaling and Workforce Composition: IV Horse Race}" ///
            "\label{tab:scaling_comp_iv}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{6}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\tiny" ///
             "\item \textit{Notes:} IV specifications instrument for remote work using WFH exposure. " ///
             "Composition interactions are also instrumented (var6×comp, var7×comp). " ///
             "All specifications include firm and year-half fixed effects. " ///
             "KP F-stat is Kleibergen-Paap weak identification test statistic. " ///
             "\end{tablenotes}" "\end{table}")

* Combined table for main paper
esttab ols1 ols2 ols3 iv1 iv2 iv3 using "$results/scaling_composition_main.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_engineer* var5_engineer* var3_sales* var5_sales*) ///
    order(var3 var5 var3_* var5_*) ///
    stats(model N, fmt(0 0) labels("Model" "Observations")) ///
    mtitles("OLS Base" "OLS Eng" "OLS Sales" "IV Base" "IV Eng" "IV Sales") ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer_share_2019 "Remote × Post × Engineer%" ///
              var5_engineer_share_2019 "Remote × Post × Startup × Engineer%" ///
              var3_sales_share_2019 "Remote × Post × Sales%" ///
              var5_sales_share_2019 "Remote × Post × Startup × Sales%")

di "Results saved to:"
di "- $results/scaling_composition_ols_horse_race.tex"
di "- $results/scaling_composition_iv_horse_race.tex"
di "- $results/scaling_composition_main.tex"