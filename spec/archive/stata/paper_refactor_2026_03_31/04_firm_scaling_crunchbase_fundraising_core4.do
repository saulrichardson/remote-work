*============================================================*
* firm_scaling_crunchbase_fundraising_core4.do
*
* Minimal Crunchbase fundraising runner for a 4-column table.
*
* Outcomes (columns)
*   (1) Any USD raised:        1{USD raised > 0} (includes seed)
*   (2) Series A+ round:       1{Series A-or-higher round in half-year}
*   (3) USD raised rank:       within-half-year percentile bin (q100, 1..100)
*   (4) USD raised (levels):   USD raised in half-year (includes zeros)
*
* Sample
*   - Keep Crunchbase-matched firms (cb_matched==1)
*   - Drop public firms (public!=1)
*
* Spec (pure)
*   y_it = β var3_it + FE_firm + FE_time + e_it
*   IV: (var3 = var6) with firm+time FE, clustered by firm
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*     (built by python src/py/build_firm_scaling_crunchbase_outcomes.py)
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_core4/
*     consolidated_results.csv
*     first_stage.csv
*     outcome_diagnostics.csv
*============================================================*

// 0) Bootstrap paths + logging
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

local specname "firm_scaling_crunchbase_fundraising_core4"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

// Dependencies (fail fast)
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

// 1) Load Crunchbase-augmented firm panel (CSV)
local in_csv "$processed_data/firm_panel_with_cb_funding.csv"
capture confirm file "`in_csv'"
if _rc {
    di as error "Missing input panel: `in_csv'"
    di as error "Build it first via:"
    di as error "  python src/py/build_firm_scaling_crunchbase_outcomes.py"
    exit 601
}

import delimited using "`in_csv'", clear varnames(1) case(preserve) stringcols(_all)

// 2) Required variables
local required_vars ///
    firm_id yh_num covid ///
    cb_matched public ///
    cb_raised_usd cb_seriesAplus_round ///
    var3 var6

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

// 3) Variable hygiene: destring numeric columns
local maybe_numeric ///
    firm_id yh_num covid ///
    cb_matched public ///
    cb_raised_usd cb_seriesAplus_round ///
    var3 var6

foreach v of local maybe_numeric {
    capture confirm variable `v'
    if !_rc {
        capture confirm numeric variable `v'
        if _rc {
            destring `v', replace ignore(" ,")
        }
    }
}

// Ensure yh_num is numeric %th for fixed effects.
capture confirm numeric variable yh_num
if _rc {
    destring yh_num, replace ignore(" ,")
}
format yh_num %th

// firm_id must be numeric for clustering; encode if needed
capture confirm numeric variable firm_id
if _rc {
    encode firm_id, gen(firm_id_num)
}
else {
    gen long firm_id_num = firm_id
}

// 4) Baseline sample policy: matched and private
keep if cb_matched == 1
keep if public != 1

// Guardrail: matched rows should use explicit zeros (not missing)
count if missing(cb_raised_usd)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing cb_raised_usd (should be 0)."
    exit 459
}

// 5) Construct outcomes (core 4)
capture drop cb_any_raised cb_raised_usd_q100
gen byte cb_any_raised = (cb_raised_usd > 0) if !missing(cb_raised_usd)
label var cb_any_raised "1{Any USD raised in half-year}"

// Percentile-rank outcome computed within the analysis sample (by half-year).
// We use q100 bins (1..100) to match the project's standard rank scale.
// NOTE: This relies on egen's xtile() function (egenmore).
capture noisily bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
if _rc {
    di as error "Unable to compute cb_raised_usd_q100 via: bys yh_num: egen ... = xtile(...), nquantiles(100)"
    di as error "This requires egenmore. Install once via:  ssc install egenmore, replace"
    exit 199
}
label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

// 6) Output dirs + postfiles
local out_dir "$results/`specname'"
capture mkdir "`out_dir'"

tempfile out_reg
capture postclose handle_reg
postfile handle_reg ///
    str16 sample_tag ///
    str8  model_type ///
    str32 outcome ///
    str16 param ///
    double coef se pval pre_mean ///
    double rkf partialF nobs ///
    using `out_reg', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str16 sample_tag ///
    str32 outcome ///
    str16 endovar ///
    str16 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

tempfile out_diag
capture postclose handle_diag
postfile handle_diag ///
    str16 sample_tag ///
    str32 outcome ///
    double n_total n_nonmiss n_missing ///
    double share_zero mean_all mean_pre ///
    using `out_diag', replace

// 7) Run regressions + diagnostics
local sample_tag "matched_private"
local outcomes cb_any_raised cb_seriesAplus_round cb_raised_usd cb_raised_usd_q100

foreach y of local outcomes {
    // Diagnostics (even if outcome is constant / regression drops)
    quietly count
    local n_total = r(N)
    quietly count if !missing(`y')
    local n_nonmiss = r(N)
    local n_missing = `n_total' - `n_nonmiss'

    quietly count if `y' == 0 & !missing(`y')
    local n_zero = r(N)
    local share_zero = .
    if `n_nonmiss' > 0 {
        local share_zero = `n_zero' / `n_nonmiss'
    }

    quietly summarize `y', meanonly
    local mean_all = r(mean)
    quietly summarize `y' if covid == 0, meanonly
    local mean_pre = r(mean)

    post handle_diag ("`sample_tag'") ("`y'") ///
        (`n_total') (`n_nonmiss') (`n_missing') ///
        (`share_zero') (`mean_all') (`mean_pre')

    // Skip regressions if outcome has no usable variation
    quietly count if !missing(`y')
    if r(N) == 0 continue
    quietly summarize `y'
    if r(sd) == 0 continue

    // OLS
    reghdfe `y' var3, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
    local N = e(N)
    local b    = _b[var3]
    local se   = _se[var3]
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_reg ("`sample_tag'") ("OLS") ("`y'") ("var3") ///
        (`b') (`se') (`pval') (`mean_pre') ///
        (.) (.) (`N')

    // IV: var3 instrumented by var6
    ivreghdfe `y' (var3 = var6), absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst
    local rkf = e(rkf)
    local N = e(N)
    matrix FS = e(first)
    local F3 = FS[4,1]

    local b    = _b[var3]
    local se   = _se[var3]
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_reg ("`sample_tag'") ("IV") ("`y'") ("var3") ///
        (`b') (`se') (`pval') (`mean_pre') ///
        (`rkf') (`F3') (`N')

    // First stage (var3)
    estimates restore _ivreg2_var3
    local N_fs = e(N)
    local b    = _b[var6]
    local se   = _se[var6]
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_fs ("`sample_tag'") ("`y'") ("var3") ("var6") ///
        (`b') (`se') (`pval') ///
        (`F3') (`rkf') (`N_fs')
}

// 8) Export
postclose handle_reg
use `out_reg', clear
export delimited using "`out_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`out_dir'/first_stage.csv", replace delimiter(",") quote

postclose handle_diag
use `out_diag', clear
export delimited using "`out_dir'/outcome_diagnostics.csv", replace delimiter(",") quote

di as result "→ Wrote: `out_dir'/consolidated_results.csv"
di as result "→ Wrote: `out_dir'/first_stage.csv"
di as result "→ Wrote: `out_dir'/outcome_diagnostics.csv"

log close _all
