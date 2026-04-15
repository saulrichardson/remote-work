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
* Scaling Regressions with Composition - Including Traditional Baseline
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
* Create standard variables
*-----------------------------------------------------------------------------*

* Traditional variables from firm_scaling.do (may already exist)
cap gen var3 = remote * covid
cap gen var4 = covid * startup  
cap gen var5 = remote * covid * startup
cap gen var6 = wfh_exposure * covid
cap gen var7 = wfh_exposure * covid * startup

*-----------------------------------------------------------------------------*
* Run regressions
*-----------------------------------------------------------------------------*

estimates clear

* Column 1: Traditional firm_scaling baseline (with firm FE)
eststo col1: reghdfe growth_rate_we var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
estadd local fe "Firm, YH"

* Column 2: Same model but without firm FE (for comparison with composition models)
eststo col2: reg growth_rate_we var3 var5 var4 i.yh, robust cluster(firm_id)
estadd local fe "YH only"

* Column 3: Simplified model focusing on startup effect
eststo col3: reg growth_rate_we startup age rent hhi_1000 i.yh if covid==1, robust
estadd local fe "None"

* Columns 4-7: Add composition interactions (covid period only)
preserve
keep if covid == 1

* Engineer composition
eststo col4: reg growth_rate_we startup c.startup#c.engineer_share_2019 ///
    age rent hhi_1000 i.yh, robust
estadd local fe "None"

* Sales composition  
eststo col5: reg growth_rate_we startup c.startup#c.sales_share_2019 ///
    age rent hhi_1000 i.yh, robust
estadd local fe "None"

* Marketing composition
eststo col6: reg growth_rate_we startup c.startup#c.marketing_share_2019 ///
    age rent hhi_1000 i.yh, robust
estadd local fe "None"

* Entry-level composition
eststo col7: reg growth_rate_we startup c.startup#c.level1_share_2019 ///
    age rent hhi_1000 i.yh, robust
estadd local fe "None"

restore

*-----------------------------------------------------------------------------*
* Export comparison table
*-----------------------------------------------------------------------------*

esttab col1 col2 col3 col4 col5 col6 col7 using "$results/scaling_baseline_comparison.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var4 startup *startup*) ///
    order(var3 var5 var4 startup *startup*) ///
    stats(fe N r2, fmt(0 0 3) labels("Fixed Effects" "Observations" "R-squared")) ///
    mtitles("Traditional" "No Firm FE" "Simple" "Engineer" "Sales" "Marketing" "Entry") ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var4 "Post × Startup" ///
              startup "Startup" ///
              c.startup#c.engineer_share_2019 "Startup × Engineer %" ///
              c.startup#c.sales_share_2019 "Startup × Sales %" ///
              c.startup#c.marketing_share_2019 "Startup × Marketing %" ///
              c.startup#c.level1_share_2019 "Startup × Entry %") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Comparison: Traditional vs. Composition-Based Scaling Analysis}" ///
            "\label{tab:scaling_comparison}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{7}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\tiny" ///
             "\item \textit{Notes:} Columns 1-2 show the traditional specification from firm\_scaling.do. " ///
             "Column 1 includes firm fixed effects, column 2 does not. " ///
             "Column 3 shows a simplified COVID-period model. " ///
             "Columns 4-7 add workforce composition interactions. " ///
             "Composition measured as pre-COVID (2019) percentage of workforce. " ///
             "\end{tablenotes}" "\end{table}")

* Also create a summary comparison
file open summ using "$results/scaling_comparison_summary.txt", write replace
file write summ "COMPARISON OF SPECIFICATIONS" _n _n
file write summ "Traditional (firm_scaling.do):" _n
file write summ "- Uses var3 (remote×covid) and var5 (remote×covid×startup)" _n
file write summ "- Includes firm fixed effects" _n
file write summ "- Identifies remote work effect" _n _n
file write summ "Composition approach:" _n
file write summ "- Uses startup indicator and startup×composition interactions" _n
file write summ "- No firm fixed effects (cross-sectional variation)" _n
file write summ "- Identifies workforce composition effects" _n _n
file write summ "Key difference: Traditional identifies remote work effects," _n
file write summ "while composition identifies workforce structure effects" _n
file close summ

di "Results saved to:"
di "- $results/scaling_baseline_comparison.tex"
di "- $results/scaling_comparison_summary.txt"