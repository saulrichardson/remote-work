*============================================================*
* firm_scaling_crunchbase.do
*
* Goal:
*   Re-run the baseline firm_scaling specification (same RHS, FE, clustering,
*   and IV instruments), but swap the LHS to a Crunchbase-derived outcome.
*
* Baseline spec (from spec/stata/firm_scaling.do):
*   OLS: reghdfe y var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
*   IV : ivreghdfe y (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
*
* This script expects a processed firm×half-year panel that already contains:
*   - var3 var4 var5 var6 var7 (canonical RHS/instruments)
*   - org_uuid + cb_* outcome columns merged from Crunchbase funding_rounds
*
* Build the input panel first (Python):
*   python src/py/build_firm_scaling_crunchbase_outcomes.py
*
* Usage:
*   do spec/stata/firm_scaling_crunchbase.do <lhs_var>
*
* Examples:
*   do spec/stata/firm_scaling_crunchbase.do cb_any_round
*   do spec/stata/firm_scaling_crunchbase.do cb_log1p_raised_usd
*   do spec/stata/firm_scaling_crunchbase.do cb_seriesAplus_round
*
* Output:
*   results/raw/firm_scaling_cb_<lhs_var>/
*     consolidated_results.csv
*     first_stage.csv
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse arguments (default LHS for GUI "Run" convenience)
* --------------------------------------------------------------------------
args lhs
if "`lhs'" == "" {
    local lhs "cb_log1p_raised_usd"
    di as text "No LHS provided; defaulting to `lhs'."
    di as text "Override via:  do spec/stata/firm_scaling_crunchbase.do <lhs_var>"
}

local specname "firm_scaling_cb_`lhs'"

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

* Dependency checks (fail fast)
capture which reghdfe
if _rc {
    di as error "Required package 'reghdfe' not found."
    di as error "Install once via:  ssc install reghdfe, replace"
    exit 199
}
capture which ivreghdfe
if _rc {
    di as error "Required package 'ivreghdfe' not found."
    di as error "Install once via:  ssc install ivreghdfe, replace"
    exit 199
}

* --------------------------------------------------------------------------
* 2) Load Crunchbase-augmented firm panel (CSV)
* --------------------------------------------------------------------------
local in_csv "$processed_data/firm_panel_with_cb_funding.csv"
capture confirm file "`in_csv'"
if _rc {
    di as error "Missing input panel: `in_csv'"
    di as error "Build it first via:"
    di as error "  python src/py/build_firm_scaling_crunchbase_outcomes.py"
    di as error "This requires data/raw/crunchbase/funding_rounds.csv (untracked)."
    exit 601
}

import delimited using "`in_csv'", clear stringcols(_all)

* Ensure RHS variables exist (and coerce to numeric)
foreach v in var3 var4 var5 var6 var7 covid startup remote teleworkable `lhs' cb_matched {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        di as error "If `v' is a Crunchbase outcome, make sure it is produced by the Python builder."
        exit 198
    }
}

foreach v in var3 var4 var5 var6 var7 covid startup remote teleworkable `lhs' cb_matched {
    capture confirm numeric variable `v'
    if _rc {
        destring `v', replace ignore(" ,")
    }
}

* Convert half-year key to Stata %th numeric for fixed effects.
* The Python-built CSV uses ISO dates like "2021-01-01" / "2021-07-01".
capture confirm variable yh_num
if _rc {
    capture confirm numeric variable yh
    if _rc {
        gen double yh_num = hofd(daily(yh, "YMD"))
    }
    else {
        gen double yh_num = yh
    }
}
else {
    capture confirm numeric variable yh_num
    if _rc {
        destring yh_num, replace ignore(" ,")
    }
}
format yh_num %th

* firm_id must be numeric for clustering; encode if needed
capture confirm numeric variable firm_id
if _rc {
    encode firm_id, gen(firm_id_num)
}
else {
    gen firm_id_num = firm_id
}

* --------------------------------------------------------------------------
* 3) Restrict sample to Crunchbase-matched firms
* --------------------------------------------------------------------------
count if cb_matched != 1
di as text "Dropping " r(N) " firm×period row(s) with cb_matched != 1 (no Crunchbase org match)."
keep if cb_matched == 1

* Verify the LHS has data after restriction
quietly summarize `lhs'
if r(N) == 0 {
    di as error "LHS `lhs' has no non-missing observations after restricting to cb_matched==1."
    di as error "Check that your funding_rounds.csv contains usable dates and org_uuid values."
    exit 200
}

drop if public == "1.0"
// keep if startup == 1

// gen var3 = remote * covid
// gen var4 = covid * startup
// gen var5 = remote * covid * startup
// gen var6 = covid * teleworkable
// gen var7 = startup * covid * teleworkable

// drop var3 var4 var5 var6 var7

// gen var3 = remote * covid
// gen var4 = covid 
// gen var5 = remote * covid 
// gen var6 = covid * teleworkable
// gen var7 = covid * teleworkable

* --------------------------------------------------------------------------
* 4) Results setup (postfiles; mirrors firm_scaling.do)
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
* 5) Main regressions (same RHS/FE/IV as firm_scaling.do)
* --------------------------------------------------------------------------
local y "`lhs'"

destring cb_round_count, replace


summarize `y' if covid == 0, meanonly
local pre_mean = r(mean)

* --- OLS ---
reghdfe cb_round_count var3, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
local N = e(N)

foreach p in var3 {
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
    cb_round_count (var3 = var6), ///
    absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst

local rkf = e(rkf)
local N = e(N)

foreach p in var3 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("`y'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') ///
        (`rkf') (`N')
}

* --- FIRST STAGE (same export logic as firm_scaling.do) ---
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
