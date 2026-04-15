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
* Scaling Composition Analysis - Final Version
* Using reghdfe for efficiency with firm FE
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

* Keep only merged observations
keep if !missing(engineer_share_2019)

*-----------------------------------------------------------------------------*
* Create composition interactions
*-----------------------------------------------------------------------------*

* Center composition variables at their means for easier interpretation
foreach var in engineer_share_2019 sales_share_2019 marketing_share_2019 level1_share_2019 {
    sum `var'
    gen `var'_c = `var' - r(mean)
}

* Create interactions with centered variables
gen var3_engineer = var3 * engineer_share_2019_c
gen var5_engineer = var5 * engineer_share_2019_c

gen var3_sales = var3 * sales_share_2019_c
gen var5_sales = var5 * sales_share_2019_c

gen var3_marketing = var3 * marketing_share_2019_c
gen var5_marketing = var5 * marketing_share_2019_c

gen var3_entry = var3 * level1_share_2019_c
gen var5_entry = var5 * level1_share_2019_c

*-----------------------------------------------------------------------------*
* Run regressions using reghdfe
*-----------------------------------------------------------------------------*

* Store results
estimates clear

* Baseline
eststo m1: reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local comp "None"

* With engineer composition
eststo m2: reghdfe growth_rate_we var3 var5 var4 var3_engineer var5_engineer, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local comp "Engineer"

* With sales composition
eststo m3: reghdfe growth_rate_we var3 var5 var4 var3_sales var5_sales, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local comp "Sales"

* With marketing composition
eststo m4: reghdfe growth_rate_we var3 var5 var4 var3_marketing var5_marketing, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local comp "Marketing"

* With entry-level composition
eststo m5: reghdfe growth_rate_we var3 var5 var4 var3_entry var5_entry, ///
    absorb(firm_id yh) vce(cluster firm_id)
estadd local comp "Entry"

*-----------------------------------------------------------------------------*
* Export results
*-----------------------------------------------------------------------------*

* Text version for review
esttab m1 m2 m3 m4 m5 using "$results/scaling_composition_results.txt", ///
    replace ///
    keep(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(comp N r2_a, fmt(0 0 3) labels("Composition" "Observations" "Adj R-sq")) ///
    mtitles("Baseline" "Engineer" "Sales" "Marketing" "Entry") ///
    nonotes addnotes("Standard errors clustered at firm level" ///
                     "All models include firm and year-half fixed effects" ///
                     "Composition variables centered at mean")

* LaTeX version
esttab m1 m2 m3 m4 m5 using "$results/scaling_composition_final.tex", ///
    replace booktabs fragment ///
    keep(var3 var5 var3_* var5_*) ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N r2_a, fmt(0 3) labels("Observations" "Adj. R-squared")) ///
    mtitles("(1)" "(2)" "(3)" "(4)" "(5)") ///
    mgroups("Baseline" "With Composition Interactions", pattern(1 1 1 1 1) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span) ///
    varlabels(var3 "Remote × Post" ///
              var5 "Remote × Post × Startup" ///
              var3_engineer "Remote × Post × Engineer\%" ///
              var5_engineer "Remote × Post × Startup × Engineer\%" ///
              var3_sales "Remote × Post × Sales\%" ///
              var5_sales "Remote × Post × Startup × Sales\%" ///
              var3_marketing "Remote × Post × Marketing\%" ///
              var5_marketing "Remote × Post × Startup × Marketing\%" ///
              var3_entry "Remote × Post × Entry\%" ///
              var5_entry "Remote × Post × Startup × Entry\%") ///
    prehead("\begin{table}[H]" "\centering" ///
            "\caption{Firm Scaling: Remote Work Effects by Workforce Composition}" ///
            "\label{tab:scaling_composition_final}" ///
            "\scriptsize" ///
            "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{5}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\scriptsize" ///
             "\item \textit{Notes:} This table examines whether remote work effects vary by pre-COVID workforce composition. " ///
             "Column 1 shows the baseline specification. Columns 2-5 add interactions between remote work variables and " ///
             "workforce composition (centered at mean). All specifications include firm and year-half fixed effects. " ///
             "Standard errors clustered at firm level. *** p$<$0.01, ** p$<$0.05, * p$<$0.10." ///
             "\end{tablenotes}" "\end{table}")

di "Results saved to:"
di "- $results/scaling_composition_results.txt"
di "- $results/scaling_composition_final.tex"