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

* Import composition data and prepare for analysis
clear all
set more off

* Import composition CSV
import delimited "results/raw/composition_sample.csv", clear

* Label variables
label var companyname "Company Name"
label var pct_chg_soc151132 "% Change Software Developers"
label var pct_chg_soc132011 "% Change Accountants"
label var pct_chg_soc119111 "% Change Medical Managers"
label var pct_chg_soc131111 "% Change Management Analysts"
label var pct_chg_soc111021 "% Change General Managers"

label var pct_chg_junior "% Change Junior Level"
label var pct_chg_senior "% Change Senior Level"
label var pct_chg_manager "% Change Manager Level"
label var pct_chg_director "% Change Director Level"

label var pct_chg_soc151132_junior "% Change Junior Software Dev"
label var pct_chg_soc151132_senior "% Change Senior Software Dev"
label var pct_chg_soc132011_manager "% Change Manager Accountants"

* Save as Stata dataset
save "results/raw/composition_sample.dta", replace

* Create fake firm panel for testing
clear
set obs 100
gen companyname = "company_" + string(_n)
gen startup = (_n <= 20)
gen age = 5 + int(runiform() * 20)
gen growth_rate_we = 0.05 + 0.1 * startup + rnormal() * 0.15
gen rent = 2000 + runiform() * 3000
gen hhi_1000 = 100 + runiform() * 900
gen yh = 2020

* Merge with composition data
merge 1:1 companyname using "results/raw/composition_sample.dta"
drop _merge

* Save merged data
save "results/raw/firm_panel_with_composition.dta", replace

display "Data preparation complete"
