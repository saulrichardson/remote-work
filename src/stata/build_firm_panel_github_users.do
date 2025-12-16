/*-------------------------------------------------------------------
| build_firm_panel_github_users.do — Firm × half-year panel from GitHub users
|
| GOAL
| ----
| Construct a firm-level panel where “employment”, “joins”, and “leaves” are
| computed *only* from the GitHub-linked worker sample (the user panels built
| by src/stata/build_all_user_panels.do).
|
| This implements “option B”: the unit of observation is firm × half-year,
| but the underlying sample is GitHub users (linked to firms via the LinkedIn
| merge upstream).
|
| INPUTS
| ------
|   data/clean/user_panel_<variant>.dta
|
| VARIANT
| -------
|   Pass a user-panel variant as the first argument (default: precovid):
|     do src/stata/build_firm_panel_github_users.do precovid
|     do src/stata/build_firm_panel_github_users.do unbalanced
|
| OUTPUTS
| -------
|   data/clean/firm_panel_github_users_<variant>.dta
|   data/samples/firm_panel_github_users_<variant>.csv   (small-ish diagnostic)
|
| DEFINITIONS (flows between t-1 and t, aligned at t)
| ---------------------------------------------------
|   headcount_t(f) = # unique GitHub users observed at firm f in half-year t
|   join_t(f)      = # users at firm f in t whose firm in t-1 is different OR
|                    who are not observed in t-1 (entry from “outside sample”)
|   leave_t(f)     = # users whose firm in t-1 is f and whose firm in t is
|                    different OR who are not observed in t (exit to “outside sample”)
|
| Rates match build_firm_panel.do (but with GitHub-user headcount):
|   growth_rate_t = headcount_t / headcount_{t-1} - 1   (only if headcount_{t-1} > 0)
|   join_rate_t   = join_t      / headcount_{t-1}       (only if headcount_{t-1} > 0)
|   leave_rate_t  = leave_t     / headcount_{t-1}       (only if headcount_{t-1} > 0)
|
| NOTES / ASSUMPTIONS
| -------------------
| - This relies on the LinkedIn↔GitHub merge in the user panel to attach firm IDs.
| - Firm attributes (remote, startup, company_teleworkable) are assumed constant
|   within firm_id across time in the user panel; we fail fast if they vary.
*-------------------------------------------------------------------*/

args user_variant
if "`user_variant'" == "" local user_variant "precovid"

do "../../spec/stata/_bootstrap.do"

local tag "github_users_`user_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/build_firm_panel_`tag'.log", replace text

* Dependency check: winsor2 -------------------------------------------------
capture which winsor2
if _rc {
    di as error "Required package 'winsor2' not found."
    di as error "Install once via:  ssc install winsor2, replace"
    exit 199
}

* --------------------------------------------------------------------------
* 1) Load GitHub-linked user panel variant
* --------------------------------------------------------------------------
capture confirm file "$processed_data/user_panel_`user_variant'.dta"
if _rc {
    di as error "Missing user panel: $processed_data/user_panel_`user_variant'.dta"
    di as error "Run src/stata/build_all_user_panels.do to generate it."
    exit 601
}

use "$processed_data/user_panel_`user_variant'.dta", clear

* Validate required variables ------------------------------------------------
cap confirm variable user_id
if _rc {
    di as error "user_panel_`user_variant'.dta missing variable user_id."
    exit 198
}
cap confirm variable firm_id
if _rc {
    di as error "user_panel_`user_variant'.dta missing variable firm_id."
    exit 198
}
cap confirm variable yh
if _rc {
    di as error "user_panel_`user_variant'.dta missing variable yh."
    exit 198
}
cap confirm string variable companyname
if _rc {
    di as error "user_panel_`user_variant'.dta missing string variable companyname."
    exit 198
}
foreach v in remote startup company_teleworkable {
    cap confirm variable `v'
    if _rc {
        di as error "user_panel_`user_variant'.dta missing required variable `v'."
        exit 198
    }
}

keep user_id firm_id companyname yh remote startup company_teleworkable
drop if missing(user_id, firm_id, yh)

* Ensure one observation per user×half-year (otherwise transitions are ambiguous)
duplicates tag user_id yh, gen(_dup_user_yh)
count if _dup_user_yh > 0
if r(N) > 0 {
    di as error "Found " r(N) " duplicate user_id×yh rows in user_panel_`user_variant'.dta."
    di as error "Join/leave definitions require unique user presence per half-year."
    exit 459
}
drop _dup_user_yh

* --------------------------------------------------------------------------
* 2) Firm attribute snapshot (assumed time-invariant within firm_id)
* --------------------------------------------------------------------------
tempfile firm_attrs curr prev head_join leave_counts panel

preserve
    keep firm_id companyname remote startup company_teleworkable

    foreach v in remote startup company_teleworkable {
        bysort firm_id: egen __min_`v' = min(`v')
        bysort firm_id: egen __max_`v' = max(`v')
        count if __min_`v' != __max_`v'
        if r(N) > 0 {
            di as error "Firm attribute `v' varies within firm_id in user_panel_`user_variant'.dta."
            di as error "This builder assumes firm attributes are constant within firm_id."
            exit 459
        }
        drop __min_`v' __max_`v'
    }

    bysort firm_id: keep if _n == 1
    save `firm_attrs', replace
restore

* --------------------------------------------------------------------------
* 3) Transition frame (align flows between t-1 and t at time t)
* --------------------------------------------------------------------------
keep user_id yh firm_id
sort user_id yh
save `curr', replace

use `curr', clear
rename firm_id firm_id_prev
replace yh = yh + 1
save `prev', replace

use `curr', clear
merge 1:1 user_id yh using `prev'

gen byte switch = (_merge == 3 & firm_id != firm_id_prev)
gen byte join_user  = (_merge == 1) | switch
gen byte leave_user = (_merge == 2) | switch

* --------------------------------------------------------------------------
* 4) Collapse to firm×half-year headcount + flows
* --------------------------------------------------------------------------
preserve
    keep if inlist(_merge, 1, 3)
    collapse (count) headcount=user_id (sum) join=join_user, by(firm_id yh)
    save `head_join', replace
restore

preserve
    keep if inlist(_merge, 2, 3)
    collapse (sum) leave=leave_user, by(firm_id_prev yh)
    rename firm_id_prev firm_id
    save `leave_counts', replace
restore

use `head_join', clear
merge 1:1 firm_id yh using `leave_counts'

replace headcount = 0 if missing(headcount)
replace join = 0 if missing(join)
replace leave = 0 if missing(leave)
drop _merge

* Fill in missing firm×time rows across the global half-year range
xtset firm_id yh
tsfill, full
replace headcount = 0 if missing(headcount)
replace join = 0 if missing(join)
replace leave = 0 if missing(leave)

* Attach firm attributes to every row (including filled-in 0-headcount periods)
merge m:1 firm_id using `firm_attrs', keep(3) nogen

* --------------------------------------------------------------------------
* 5) Rates + regressors (mirror build_firm_panel.do conventions)
* --------------------------------------------------------------------------
gen covid = yh >= 120   // 120 = 2020H1 in Stata half-year dates

xtset firm_id yh
gen headcount_lag = L.headcount

gen growth_rate = (headcount / headcount_lag) - 1 if headcount_lag > 0
gen join_rate   = join / headcount_lag           if headcount_lag > 0
gen leave_rate  = leave / headcount_lag          if headcount_lag > 0

winsor2 growth_rate join_rate leave_rate, cuts(1 99) suffix(_we)
label variable growth_rate_we "GitHub-user growth rate (winsorized [1,99])"
label variable join_rate_we   "GitHub-user join rate (winsorized [1,99])"
label variable leave_rate_we  "GitHub-user leave rate (winsorized [1,99])"

drop growth_rate join_rate leave_rate

* Main interactions (same naming as existing specs)
gen var3 = remote * covid
gen var4 = covid * startup
gen var5 = remote * covid * startup
gen var6 = covid * company_teleworkable
gen var7 = startup * covid * company_teleworkable

* Enforce a common sample across the three outcomes + regressors
local keep_vars ///
    firm_id yh covid remote startup company_teleworkable ///
    headcount join leave ///
    growth_rate_we join_rate_we leave_rate_we ///
    var3 var4 var5 var6 var7

egen miss_ct = rowmiss(`keep_vars')
keep if miss_ct == 0
drop miss_ct

* --------------------------------------------------------------------------
* 6) Persist
* --------------------------------------------------------------------------
local out_base = "$processed_data/firm_panel_`tag'"
save "`out_base'.dta", replace
export delimited "$PROJECT_ROOT/data/samples/firm_panel_`tag'.csv", replace

di as result "✓ Wrote GitHub-user firm panel: `out_base'.dta"
di as result "  rows: " _N

log close
