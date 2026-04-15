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

*============================================================*
* scaling_composition_roles_fixed.do
* Role-specific scaling regressions
*============================================================*

clear all
set more off

// First load and prepare the CSV data
import delimited "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/role_k7_scaling_growth.csv", clear

// The CSV already has year and half columns
// Just create yh to match firm_panel format
gen yh = yh(year, half)

// Save as temp file
tempfile role_data
save `role_data'

// Now load firm panel
use "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/firm_panel.dta", clear

// Merge with role data
merge 1:m companyname yh using `role_data'
keep if _merge == 3
drop _merge

// Generate interaction variables
gen var3 = covid * remote
gen var4 = covid  
gen var5 = covid * teleworkable
gen var6 = teleworkable
gen var7 = teleworkable * covid

// Run regression for each role
levelsof role_k7, local(roles)
foreach role in `roles' {
    di _n "========================================"
    di "Role: `role'"
    di "========================================"
    
    // Count observations
    count if role_k7 == "`role'" & !missing(pct_growth_role)
    
    // Run regression
    reghdfe pct_growth_role var3 var5 var4 if role_k7 == "`role'", absorb(firm_id yh) vce(cluster firm_id)
}