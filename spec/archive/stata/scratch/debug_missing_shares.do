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
* Debug missing share values issue
*============================================================*

clear all
set more off

// Globals
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"

// Replicate the exact steps from user_productivity_composition.do
use "$processed_data/user_panel_precovid.dta", clear
display "Starting user panel: `=_N' observations"

tempfile user_data
save `user_data'

// Prepare role share data (same as in main script)
import delimited "$processed_data/role_k7_scaling_growth.csv", clear
gen yh = yh(year, half)

// Share wide
keep companyname yh role_k7 role_share
reshape wide role_share, i(companyname yh) j(role_k7) string
rename role_share* share_*
tempfile role_share_wide
save `role_share_wide'

// Now merge with user data
use `user_data', clear
display "User data before merge: `=_N' observations"

capture drop _merge
merge m:1 companyname yh using `role_share_wide'
display "Merge results:"
tab _merge

keep if _merge == 1 | _merge == 3
drop _merge
display "After keeping unmatched + matched: `=_N' observations"

// Check what share variables exist
describe share_*

// Check missing values BEFORE zero-fill
display "Missing values BEFORE zero-fill:"
foreach var of varlist share_* {
    count if missing(`var')
    display "`var': " r(N) " missing"
}

// Apply zero-fill (same logic as main script)
capture confirm variable share_*
if _rc == 0 {
    unab sharevars: share_*
    foreach v of local sharevars {
        quietly replace `v' = 0 if missing(`v')
    }
}

// Check missing values AFTER zero-fill
display "Missing values AFTER zero-fill:"
foreach var of varlist share_* {
    count if missing(`var')
    display "`var': " r(N) " missing"
}

// Check other key variables
display "Checking other key variables:"
count if missing(covid)
display "covid missing: " r(N)

count if missing(startup)
display "startup missing: " r(N)

count if missing(total_contributions_q100)
display "total_contributions_q100 missing: " r(N)

// Test Admin interaction creation specifically
display "Testing Admin interaction creation:"
capture confirm variable share_Admin
if _rc == 0 {
    display "share_Admin exists"
    
    // Check what happens when we create interactions
    gen test_admin_covid = covid * share_Admin
    gen test_admin_inter = covid * share_Admin * startup
    
    count if missing(test_admin_covid)
    display "test_admin_covid missing: " r(N)
    
    count if missing(test_admin_inter) 
    display "test_admin_inter missing: " r(N)
    
    // Compare components
    count if missing(covid) | missing(share_Admin)
    display "covid OR share_Admin missing: " r(N)
    
    count if missing(covid) | missing(share_Admin) | missing(startup)
    display "covid OR share_Admin OR startup missing: " r(N)
} else {
    display "share_Admin does NOT exist!"
}

display "Final sample size: `=_N'"