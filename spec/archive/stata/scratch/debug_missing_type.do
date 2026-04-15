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
* Debug what type of "missing" values these are
*============================================================*

clear all
set more off

// Globals  
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"

// Replicate setup to the zero-fill point
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

// Investigate what's in the "missing" values
display "Investigating share_Admin missing values:"

// Check if they're actually numeric missing
count if share_Admin == .
display "share_Admin == . (standard missing): " r(N)

count if share_Admin == .a  
display "share_Admin == .a (extended missing a): " r(N)

count if share_Admin == .b
display "share_Admin == .b (extended missing b): " r(N)

// Check if they're string values that got imported wrong
count if share_Admin < .
display "share_Admin < . (non-missing numeric): " r(N)

// Look at some actual values
display "First 10 values of share_Admin:"
list share_Admin in 1/10

display "Some missing share_Admin values:"
list companyname yh share_Admin if missing(share_Admin) in 1/5

// Test replace logic specifically
display "Testing replace logic:"
count if missing(share_Admin)
display "Before: missing share_Admin = " r(N)

replace share_Admin = 0 if missing(share_Admin)

count if missing(share_Admin) 
display "After: missing share_Admin = " r(N)

count if share_Admin == 0
display "share_Admin == 0: " r(N)