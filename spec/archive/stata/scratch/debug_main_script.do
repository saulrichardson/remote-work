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
* Replicate exactly the main script sequence to find the bug
*============================================================*

clear all
set more off

// Globals
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "user_productivity_composition"
local result_dir "$results/`specname'"

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear
tempfile user_data
save `user_data'

// Role growth (skip)
import delimited "$processed_data/role_k7_scaling_growth.csv", clear
gen yh = yh(year, half)
preserve
    keep companyname yh role_k7 pct_growth_role
    reshape wide pct_growth_role, i(companyname yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    tempfile role_growth_wide
    save `role_growth_wide'
restore

// Role share wide
keep companyname yh role_k7 role_share
reshape wide role_share, i(companyname yh) j(role_k7) string
rename role_share* share_*
tempfile role_share_wide
save `role_share_wide'

// PART A2: Role Composition Controls (Shares) - EXACT REPLICATION

// Reload user data and merge with role shares
use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `role_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

display "BEFORE zero-fill:"
count if missing(share_Admin)
display "share_Admin missing: " r(N)

// Fill missing role shares with 0 when any share is present for the firm×half-year
// This prevents listwise deletion from spurious missings created by growth-file filters
capture confirm variable share_*
display "capture confirm result: " _rc
if _rc == 0 {
    display "Entering zero-fill block"
    // Unconditionally set missing shares to 0 to retain rows in regressions
    unab sharevars: share_*
    display "Share variables found: " "`sharevars'"
    foreach v of local sharevars {
        display "Processing variable: `v'"
        count if missing(`v')
        local before = r(N)
        display "  Before replace: `before' missing"
        replace `v' = 0 if missing(`v')
        count if missing(`v')
        local after = r(N)
        display "  After replace: `after' missing"
    }
} else {
    display "share_* variables not found! _rc = " _rc
}

display "AFTER zero-fill:"
count if missing(share_Admin)
display "share_Admin missing: " r(N)