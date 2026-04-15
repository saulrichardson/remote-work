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
* Create LaTeX table for composition results
*=============================================================================*

clear all
set more off

global results "results/raw"
global cleaned "results/cleaned"

* Load saved estimates or re-run if needed
use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)
keep if covid == 1
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

estimates clear

* Re-run regressions
eststo col1: reg growth_rate_we startup age rent hhi_1000 i.yh, robust

local roles "engineer sales finance marketing admin operations scientist"
local i = 2
foreach var of local roles {
    eststo col`i': reg growth_rate_we startup `var'_share_2019 c.startup#c.`var'_share_2019 ///
        age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

local seniority "level1 level2 level3 level4"
foreach var of local seniority {
    eststo col`i': reg growth_rate_we startup `var'_share_2019 c.startup#c.`var'_share_2019 ///
        age rent hhi_1000 i.yh, robust
    local i = `i' + 1
}

* Create main LaTeX table for paper
esttab col1 col2 col3 col4 col5 col9 col10 using "$cleaned/scaling_composition_precovid.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup engineer_share_2019 c.startup#c.engineer_share_2019 ///
         sales_share_2019 c.startup#c.sales_share_2019 ///
         finance_share_2019 c.startup#c.finance_share_2019 ///
         marketing_share_2019 c.startup#c.marketing_share_2019 ///
         level1_share_2019 c.startup#c.level1_share_2019 ///
         level2_share_2019 c.startup#c.level2_share_2019) ///
    order(startup *_share_2019 *startup*) ///
    mtitles("Baseline" "Engineer" "Sales" "Finance" "Marketing" "Entry" "Mid/Senior") ///
    mgroups("" "Role Composition" "Seniority Composition", pattern(1 1 1 1 1 1 1) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span) ///
    stats(controls N r2, fmt(0 0 3) ///
          labels("Controls" "Observations" "R-squared")) ///
    prehead("\begin{table}[H]" "\centering" "\caption{Firm Scaling and Pre-COVID Workforce Composition}" ///
            "\label{tab:scaling_composition}" "\scriptsize" "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{7}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" ///
             "\begin{tablenotes}[flushleft]" "\scriptsize" ///
             "\item \textit{Notes:} This table examines how pre-COVID (2019) workforce composition affects firm growth during COVID. " ///
             "The dependent variable is employment growth rate (winsorized). " ///
             "Composition shares are measured as percentages (0-100) of the firm's 2019 workforce. " ///
             "All specifications include controls for firm age, rent costs, market concentration (HHI), and year-half fixed effects. " ///
             "Standard errors are robust to heteroskedasticity. " ///
             "*** p$<$0.01, ** p$<$0.05, * p$<$0.10." ///
             "\end{tablenotes}" "\end{table}")

* Also create full results table for appendix
esttab col* using "$cleaned/scaling_composition_precovid_full.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *_share_2019 *startup*) ///
    order(startup *_share_2019 *startup*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Base" "Eng" "Sales" "Fin" "Mkt" "Admin" "Ops" "Sci" "L1" "L2" "L3" "L4") ///
    prehead("\begin{table}[H]" "\centering" "\caption{Firm Scaling and Pre-COVID Workforce Composition — Full Results}" ///
            "\label{tab:scaling_composition_full}" "\tiny" "\begin{adjustbox}{max width=\linewidth}" ///
            "\begin{tabular}{l*{12}{c}}") ///
    postfoot("\bottomrule" "\end{tabular}" "\end{adjustbox}" "\end{table}")

di "LaTeX tables saved to $cleaned/"