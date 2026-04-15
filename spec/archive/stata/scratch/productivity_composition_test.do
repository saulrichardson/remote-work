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

* Productivity Regressions with Composition Controls
* Testing specifications with role/seniority changes

clear all
set more off

* Create fake user-level panel for testing
clear
set obs 10000
gen user_id = _n
gen firm_id = 1 + int((_n-1)/100)  // 100 users per firm
gen companyname = "company_" + string(firm_id)
gen yh = 2020 + int(runiform() * 2)

* Create productivity and remote work variables
gen total_contributions_q100 = 50 + rnormal() * 20
gen var3 = runiform()  // Remote work measure
gen var4 = rnormal()   // Control
gen var5 = runiform()  // Another measure

* Create instruments
gen var6 = var3 + rnormal() * 0.1
gen var7 = var5 + rnormal() * 0.1

* Merge with composition data
merge m:1 companyname using "results/raw/composition_sample.dta"
drop if _merge != 3
drop _merge

* Create interaction terms
gen var3_comp = var3 * pct_chg_soc151132
gen var5_comp = var5 * pct_chg_soc151132
gen var6_comp = var6 * pct_chg_soc151132
gen var7_comp = var7 * pct_chg_soc151132

* Run productivity regressions

* Column 1: Baseline (no composition controls)
eststo clear
eststo col1: ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4, ///
    absorb(firm_id#user_id yh) ///
    cluster(user_id)

* Column 2: Control for software developer changes
eststo col2: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
    var4 pct_chg_soc151132, ///
    absorb(firm_id#user_id yh) ///
    cluster(user_id)

* Additional columns would follow same pattern...

* Export results
esttab col1 col2 using "results/raw/productivity_results_test.txt", ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_comp var5_comp pct_chg_*) ///
    stats(N, fmt(0)) ///
    mtitles("Baseline" "Software") ///
    replace

display "Productivity regressions complete"
