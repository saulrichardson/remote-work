*============================================================*
* firm_scaling_github_sample.do
*
* Goal:
*   Re-run the baseline firm_scaling specification (growth/join/leave rates)
*   but restrict the firm panel to the set of firms that appear in the
*   *GitHub user panel* (i.e., the LinkedIn↔GitHub merged worker sample).
*
* Why this exists:
*   firm_scaling.do reads data/clean/firm_panel.dta, which is built from
*   Scoop firm-level sources and therefore includes many firms that do NOT
*   appear in the GitHub-linked worker panel used by user_productivity.do.
*   This spec lets us run the *same* regression on the intersection sample.
*
* Sample definition:
*   Firms are included iff their company name appears in:
*     data/clean/user_panel_<user_variant>.dta
*
*   Supported variants depend on what you've built via
*   src/stata/build_all_user_panels.do (typically: unbalanced, balanced,
*   precovid, balanced_pre).
*
* Usage:
*   do spec/stata/firm_scaling_github_sample.do [user_variant]
*
* Examples:
*   do spec/stata/firm_scaling_github_sample.do precovid
*   do spec/stata/firm_scaling_github_sample.do unbalanced
*
* Outputs:
*   results/raw/firm_scaling_github_<user_variant>/
*     consolidated_results.csv
*     first_stage.csv
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional user-panel variant argument (default: precovid)
* --------------------------------------------------------------------------
args user_variant
if "`user_variant'" == "" local user_variant "precovid"
local specname "firm_scaling_github_`user_variant'"

* --------------------------------------------------------------------------
* 1) Bootstrap paths + logging
* --------------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

* --------------------------------------------------------------------------
* 2) Build GitHub firm list from the user panel variant
* --------------------------------------------------------------------------
tempfile firm_panel_tmp github_firms

* Load firm panel (master)
use "$processed_data/firm_panel.dta", clear
cap confirm string variable companyname
if _rc {
    di as error "firm_panel.dta is missing string variable 'companyname'."
    di as error "This script filters by firm name; rebuild firm_panel.dta with companyname retained."
    exit 198
}

* Normalise key for robust joins (case + whitespace)
gen strL companyname_key = lower(strtrim(companyname))
save `firm_panel_tmp', replace

* Load user panel variant (GitHub-linked worker panel)
capture confirm file "$processed_data/user_panel_`user_variant'.dta"
if _rc {
    di as error "Missing user panel: $processed_data/user_panel_`user_variant'.dta"
    di as error "Run src/stata/build_all_user_panels.do and ensure it writes user_panel_`user_variant'.dta."
    exit 601
}

use "$processed_data/user_panel_`user_variant'.dta", clear
cap confirm string variable companyname
if _rc {
    di as error "user_panel_`user_variant'.dta is missing string variable 'companyname'."
    exit 198
}

gen strL companyname_key = lower(strtrim(companyname))
keep companyname_key
drop if missing(companyname_key)
duplicates drop companyname_key, force
save `github_firms', replace

* --------------------------------------------------------------------------
* 3) Restrict firm panel to GitHub firm list and report overlap diagnostics
* --------------------------------------------------------------------------
use `firm_panel_tmp', clear
merge m:1 companyname_key using `github_firms'

* Overlap diagnostics (firm-level counts)
preserve
    keep if _merge == 2
    count
    local github_only = r(N)
restore

preserve
    keep if _merge == 3
    bysort companyname_key: keep if _n == 1
    count
    local matched_firms = r(N)
restore

preserve
    keep if _merge == 1
    bysort companyname_key: keep if _n == 1
    count
    local firm_only = r(N)
restore

di as txt "GitHub firm restriction via user_panel_`user_variant'.dta:"
di as txt "  matched firms (in both firm_panel + user_panel): " `matched_firms'
di as txt "  user-panel firms missing from firm_panel:        " `github_only'
di as txt "  firm-panel firms not in user-panel:              " `firm_only'

keep if _merge == 3
drop _merge
drop companyname_key

* Validate required variables exist post-filter (fail fast)
foreach v in firm_id yh covid var3 var4 var5 var6 var7 growth_rate_we join_rate_we leave_rate_we {
    cap confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' after applying GitHub firm restriction."
        di as error "Check that data/clean/firm_panel.dta was built by src/stata/build_firm_panel.do."
        exit 198
    }
}

* --------------------------------------------------------------------------
* 4) Results setup (postfiles)
* --------------------------------------------------------------------------
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

* --------------------------------------------------------------------------
* 5) Main regressions (mirrors spec/stata/firm_scaling.do)
* --------------------------------------------------------------------------
local outcome_vars growth_rate_we join_rate_we leave_rate_we
local fs_done = 0

foreach y of local outcome_vars {
    di as text "→ Processing `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    * --- OLS ---
    reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    * --- IV (2nd stage) ---
    ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst

    local rkf = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    * --- FIRST STAGE (once) ---
    if !`fs_done' {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        estimates restore _ivreg2_var3
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var3") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F3') (`rkf') (`N_fs')
        }

        estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var5") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F5') (`rkf') (`N_fs')
        }

        local fs_done 1
    }
}

* --------------------------------------------------------------------------
* 6) Export
* --------------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
capture log close
