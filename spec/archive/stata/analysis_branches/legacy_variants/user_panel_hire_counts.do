*------------------------------------------------------------*
* user_panel_hire_counts.do
* Quick sanity check of panel size and hire-event counts.
* Defaults to the precovid user panel.
*------------------------------------------------------------*

* Optional arg: panel variant suffix (e.g., precovid, balanced)
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

* Bootstrap paths
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

local specname "user_panel_hire_counts_`panel_variant'"
cap mkdir "$LOG_DIR"
capture log close
log using "$LOG_DIR/`specname'.log", replace text

di as text "Loading $processed_data/user_panel_`panel_variant'.dta"
use "$processed_data/user_panel_`panel_variant'.dta", clear

* Base panel counts
count
local N = r(N)
egen tag_user = tag(user_id)
count if tag_user
local N_user = r(N)
egen tag_firm = tag(firm_id)
count if tag_firm
local N_firm = r(N)

* Hire detection: first period where firm_id changes vs prior half-year
sort user_id yh
by user_id: gen byte hire_event = (_n>1 & firm_id != firm_id[_n-1])
count if hire_event
local N_hires = r(N)

di as result "Base panel: `N' user-half-year rows"
di as result "Unique users: `N_user'"
di as result "Unique firms: `N_firm'"
di as result "Hire events (firm_id change vs prior half-year): `N_hires'"

log close
