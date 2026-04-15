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
* Test the shares zero-fill fix specifically
*============================================================*

clear all
set more off

// Globals
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"

// Replicate Part A2 setup exactly
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

// Part A2: Role Composition Controls (Shares) - EXACT REPLICATION
use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `role_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

display "BEFORE zero-fill:"
count if missing(share_Admin)
display "share_Admin missing: " r(N)

// Apply the CORRECTED zero-fill logic
capture unab sharevars: share_*
display "capture unab result: " _rc
if _rc == 0 {
    display "Entering zero-fill block with corrected logic"
    foreach v of local sharevars {
        display "Processing variable: `v'"
        count if missing(`v')
        local before = r(N)
        display "  Before replace: `before' missing"
        replace `v' = 0 if missing(`v')
        count if missing(`v')
        local after = r(N)
        display "  After replace: `after' missing" 
        local changed = `before' - `after'
        display "  Changed: `changed' values"
    }
} else {
    display "share_* variables not found! _rc = " _rc
}

display "AFTER zero-fill:"
count if missing(share_Admin)
display "share_Admin missing: " r(N)

// Test Admin interaction creation
display "Testing Admin interaction creation with zero-filled data:"
gen Admin_share_covid = covid * share_Admin
gen Admin_share_inter = covid * share_Admin * startup

count if missing(Admin_share_covid)
display "Admin_share_covid missing: " r(N)

count if missing(Admin_share_inter)
display "Admin_share_inter missing: " r(N)

display "Final sample size: `=_N'"