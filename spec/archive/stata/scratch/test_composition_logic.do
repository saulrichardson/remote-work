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
* Test composition regression logic with the data we just created
*=============================================================================*

clear all
set more off

global raw_data "data/raw"
global processed_data "data/processed"
global results "results/raw"

* Import the composition data we just created
import delimited "$results/firm_soc_composition.csv", clear
save "$results/temp_soc_comp.dta", replace

* Test 1: Check if we can merge with firm panel
use "$processed_data/firm_panel.dta", clear
keep if yh >= 4040  // 2020 onwards
keep companyname yh growth_rate_we startup age rent hhi_1000 covid

merge m:1 companyname using "$results/temp_soc_comp.dta"
tab _merge

* Keep only matched firms
keep if _merge == 3
drop _merge

* Test 2: Simple scaling regression with composition
di _n "=== Test Scaling Regression ==="
reg growth_rate_we startup pct_chg_soc1511 pct_chg_soc1320 if covid == 1

* Test 3: With interactions
di _n "=== Test with Interactions ==="
reg growth_rate_we startup c.startup#c.pct_chg_soc1511 c.startup#c.pct_chg_soc1320 if covid == 1

* Display sample statistics
di _n "=== Sample Statistics ==="
sum growth_rate_we startup pct_chg_soc* if covid == 1

* Test 4: Check if we have enough variation
foreach v of varlist pct_chg_soc* {
    quietly sum `v' if covid == 1
    if r(sd) > 0 {
        di "`v': mean=" %6.2f r(mean) ", sd=" %6.2f r(sd) ", N=" r(N)
    }
}

* Clean up
erase "$results/temp_soc_comp.dta"

di _n "Test complete - logic verified!"