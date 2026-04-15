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

global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
use "$processed_data/user_panel_precovid.dta", clear
tempfile user_data
save `user_data'

import delimited "$processed_data/role_k7_scaling_growth.csv", clear
gen yh = yh(year, half)
keep companyname yh role_k7 role_share
reshape wide role_share, i(companyname yh) j(role_k7) string
rename role_share* share_*
tempfile role_share_wide
save `role_share_wide'

use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `role_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

describe share_*

// Test different ways to confirm variables exist
display "Test 1: capture confirm variable share_*"
capture confirm variable share_*
display "_rc = " _rc

display "Test 2: capture confirm variable share_Admin"  
capture confirm variable share_Admin
display "_rc = " _rc

display "Test 3: capture unab sharevars: share_*"
capture unab sharevars: share_*
display "_rc = " _rc
if _rc == 0 {
    display "sharevars = `sharevars'"
}