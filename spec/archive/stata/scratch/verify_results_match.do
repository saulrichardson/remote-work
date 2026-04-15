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

* Quick check to verify CSV matches log output

import delimited "../results/cleaned/growth_mechanisms_results.csv", clear

di _n "=== BASELINE IV SEPARATE FE ==="
list if spec_name == "baseline_iv_sep"

di _n "=== ALL IV RESULTS ==="
keep if strpos(spec_name, "_iv_")
list spec_name var3_coef var3_se n_obs rkf