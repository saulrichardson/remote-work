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
* Scaling Regressions - Composition through startup interaction only
* Corrected: No standalone composition effect
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

* Keep COVID period
keep if covid == 1

* Merge composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

*-----------------------------------------------------------------------------*
* Run regressions - composition only through startup interaction
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Baseline
eststo col1: reg growth_rate_we startup age rent hhi_1000 i.yh, robust

* Columns 2-8: Add startup×composition interaction for each role
local roles "engineer sales finance marketing admin operations scientist"
local i = 2
foreach var of local roles {
    * Only include the interaction term, not standalone composition
    eststo col`i': reg growth_rate_we startup c.startup#c.`var'_share_2019 ///
        age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

* Columns 9-12: Add startup×seniority interactions
local seniority "level1 level2 level3 level4"
foreach var of local seniority {
    eststo col`i': reg growth_rate_we startup c.startup#c.`var'_share_2019 ///
        age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

*-----------------------------------------------------------------------------*
* Export results - cleaner version
*-----------------------------------------------------------------------------*

* Main paper table
esttab col1 col2 col3 col5 col9 col10 using "$results/scaling_composition_clean.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *startup*) ///
    order(startup *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry" "Mid/Senior") ///
    varlabels(c.startup#c.engineer_share_2019 "Startup × Engineer %" ///
              c.startup#c.sales_share_2019 "Startup × Sales %" ///
              c.startup#c.marketing_share_2019 "Startup × Marketing %" ///
              c.startup#c.level1_share_2019 "Startup × Entry level %" ///
              c.startup#c.level2_share_2019 "Startup × Mid/Senior %") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Startup Scaling and Workforce Composition}" ///
            "\label{tab:scaling_composition_clean}" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{6}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\scriptsize" ///
             "\item \textit{Notes:} Dependent variable is employment growth rate during COVID. " ///
             "Composition measured as pre-COVID (2019) percentage of workforce. " ///
             "Regressions include only the startup main effect and startup×composition interactions, " ///
             "not standalone composition effects. Controls: firm age, rent, HHI, year-half FE. " ///
             "Robust standard errors. *** p$<$0.01, ** p$<$0.05, * p$<$0.10." ///
             "\end{tablenotes}" "\end{table}")

di "Clean results saved to: $results/scaling_composition_clean.tex"