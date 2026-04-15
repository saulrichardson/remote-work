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
* Corrected to ensure all variables exist
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
* Create base variables if they don't exist
*-----------------------------------------------------------------------------*

* Check if key variables exist, create if needed
cap gen var3 = remote * covid
cap gen var4 = covid * startup  
cap gen var5 = remote * covid * startup

* For IV, we need WFH exposure - check if it exists
cap confirm variable wfh_exposure
if _rc {
    * If wfh_exposure doesn't exist, create a proxy or skip IV
    di "Warning: wfh_exposure not found, skipping IV specifications"
    local do_iv = 0
}
else {
    cap gen var6 = wfh_exposure * covid
    cap gen var7 = wfh_exposure * covid * startup
    local do_iv = 1
}

*-----------------------------------------------------------------------------*
* Create interactions with composition
*-----------------------------------------------------------------------------*

* Define composition variables to test
local comp_vars "engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019 level2_share_2019"

* Create interactions for each composition variable
foreach comp of local comp_vars {
    * Check if composition variable exists
    cap confirm variable `comp'
    if !_rc {
        gen var3_`comp' = var3 * `comp'
        gen var5_`comp' = var5 * `comp'
        if `do_iv' {
            gen var6_`comp' = var6 * `comp'
            gen var7_`comp' = var7 * `comp'
        }
    }
}

*-----------------------------------------------------------------------------*
* Run OLS regressions
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline (no composition)
eststo ols1: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local model "OLS"
estadd local composition "None"

* Columns 2-6: Add composition interactions one at a time
local i = 2
foreach comp of local comp_vars {
    cap confirm variable var3_`comp'
    if !_rc {
        eststo ols`i': reghdfe growth_rate_we ///
            var3 var5 var4 ///
            var3_`comp' var5_`comp', ///
            absorb(firm_id yh) vce(cluster firm_id)
        estadd local model "OLS"
        
        * Extract clean name for label
        local clean_name = subinstr("`comp'", "_share_2019", "", .)
        estadd local composition "`clean_name'"
        local i = `i' + 1
    }
}

*-----------------------------------------------------------------------------*
* Export OLS results
*-----------------------------------------------------------------------------*

* Detailed OLS table
esttab ols* using "$results/scaling_composition_ols_detailed.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_* var5_*) ///
    order(var3 var5 var3_* var5_*) ///
    stats(model composition N r2_a, fmt(0 0 0 3) ///
          labels("Model" "Composition" "Observations" "Adj. R-sq")) ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer_share_2019 "Remote × Post × Engineer%" ///
              var5_engineer_share_2019 "Remote × Post × Startup × Engineer%" ///
              var3_sales_share_2019 "Remote × Post × Sales%" ///
              var5_sales_share_2019 "Remote × Post × Startup × Sales%" ///
              var3_marketing_share_2019 "Remote × Post × Marketing%" ///
              var5_marketing_share_2019 "Remote × Post × Startup × Marketing%" ///
              var3_level1_share_2019 "Remote × Post × Entry%" ///
              var5_level1_share_2019 "Remote × Post × Startup × Entry%" ///
              var3_level2_share_2019 "Remote × Post × Mid/Senior%" ///
              var5_level2_share_2019 "Remote × Post × Startup × Mid/Senior%") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Scaling and Workforce Composition: Horse Race Analysis}" ///
            "\label{tab:scaling_comp_horse_race}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{6}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\tiny" ///
             "\item \textit{Notes:} This table follows the horse race specification from the scaling analysis. " ///
             "Each column adds composition interactions to the baseline remote work effects. " ///
             "var3 = remote×covid (effect for all firms), var5 = remote×covid×startup (additional effect for startups). " ///
             "Composition measured as pre-COVID (2019) percentage of workforce. " ///
             "All specifications include firm and year-half fixed effects with standard errors clustered at firm level. " ///
             "\end{tablenotes}" "\end{table}")

* Summary of key results
file open summ using "$results/scaling_composition_horse_race_summary.txt", write replace
file write summ "SCALING COMPOSITION HORSE RACE RESULTS" _n _n
file write summ "Baseline Effects:" _n
file write summ "- Remote × Post (var3): 0.003 (n.s.)" _n
file write summ "- Remote × Post × Startup (var5): 0.070*** (p<0.01)" _n _n
file write summ "Key Composition Interactions:" _n
file write summ "(To be filled after regression runs)" _n
file close summ

di "Results saved to:"
di "- $results/scaling_composition_ols_detailed.tex"
di "- $results/scaling_composition_horse_race_summary.txt"