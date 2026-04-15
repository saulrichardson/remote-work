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

* Scaling Regressions with Role × Seniority Composition
* Testing column-by-column specifications

clear all
set more off
use "results/raw/firm_panel_with_composition.dta", clear

* Store results
estimates clear

* Column 1: Baseline
reg growth_rate_we startup age rent hhi_1000 i.yh, robust
estimates store col1

* Columns 2-6: Individual roles
local roles "pct_chg_soc151132 pct_chg_soc132011 pct_chg_soc119111 pct_chg_soc131111 pct_chg_soc111021"
local i = 2
foreach var of local roles {
    reg growth_rate_we startup age rent hhi_1000 `var' c.startup#c.`var' i.yh, robust
    estimates store col`i'
    local i = `i' + 1
}

* Columns 7-10: Seniority levels
local seniority "pct_chg_junior pct_chg_senior pct_chg_manager pct_chg_director"
local i = 7
foreach var of local seniority {
    reg growth_rate_we startup age rent hhi_1000 `var' c.startup#c.`var' i.yh, robust
    estimates store col`i'
    local i = `i' + 1
}

* Columns 11-13: Role × Seniority interactions
local interactions "pct_chg_soc151132_junior pct_chg_soc151132_senior pct_chg_soc132011_manager"
local i = 11
foreach var of local interactions {
    reg growth_rate_we startup age rent hhi_1000 `var' c.startup#c.`var' i.yh, robust
    estimates store col`i'
    local i = `i' + 1
}

* Display results table
esttab col1 col2 col3 col4 col5 col6 using "results/raw/scaling_results_test.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup pct_chg_* *startup*) ///
    order(startup pct_chg_*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Baseline" "Software" "Account" "Medical" "Mgmt Anal" "Gen Mgr") ///
    replace

esttab col7 col8 col9 col10 col11 col12 col13 using "results/raw/scaling_results_test2.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup pct_chg_* *startup*) ///
    order(startup pct_chg_*) ///
    stats(N r2, fmt(0 3)) ///
    mtitles("Junior" "Senior" "Manager" "Director" "Jr Dev" "Sr Dev" "Mgr Acct") ///
    replace

display "Scaling regressions complete"
