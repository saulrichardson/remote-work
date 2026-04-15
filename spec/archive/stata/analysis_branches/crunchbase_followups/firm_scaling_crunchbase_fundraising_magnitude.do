*============================================================*
* firm_scaling_crunchbase_fundraising_magnitude.do
*
* PI follow-ups: magnitudes, zeros, and percentile outcomes (half-year panel)
* -------------------------------------------------------------------------
* This file is a focused "next meeting" runner for the new asks:
*   (2) Paired dollars specs: with zeros vs without zeros (no log(1+x) reliance)
*   (3) Percentile-rank outcomes (and q100 bins) under the same restrictions
*
* It intentionally avoids geography (NY/SF) and compensation asks.
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*
* Baseline sample policy (mirrors canonical fundraising)
*   - keep if cb_matched==1
*   - drop public firms (public!=1)
*
* Spec (pure version; drops Startup×Post control var4)
*   y_it = β var3_it + FE_firm + FE_time + e_it
*   IV: (var3 = var6) with firm+time FE, clustered by firm
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_magnitude/
*     consolidated_results.csv
*     first_stage.csv
*     outcome_diagnostics.csv
*     sample_sizes.csv
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

local specname "firm_scaling_crunchbase_fundraising_magnitude"
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

// 2) Required variables (we need age for age restrictions)
local required_vars ///
    firm_id yh_num covid age ///
    hqstate ///
    cb_matched public ///
    cb_raised_usd cb_log1p_raised_usd ///
    cb_log1p_cum_raised_usd ///
    cb_seriesAplus_round cb_seriesAplus_cum ///
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
    firm_id yh_num covid age ///
    cb_matched public ///
    cb_raised_usd cb_log1p_raised_usd ///
    cb_log1p_cum_raised_usd ///
    cb_seriesAplus_round cb_seriesAplus_cum ///
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
    di as error "Found " r(N) " matched row(s) with missing cb_raised_usd (should be 0)."
    exit 459
}

// Snapshot the baseline dataset once; we will branch into restrictions from this.
tempfile base
save `base', replace

// 5) Output dirs + postfiles
local out_dir "$results/`specname'"
capture mkdir "`out_dir'"

tempfile out_reg
capture postclose handle_reg
postfile handle_reg ///
    str16 sample_tag ///
    str24 spec_tag ///
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
    str24 spec_tag ///
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
    str24 spec_tag ///
    str32 outcome ///
    double n_total n_nonmiss n_missing ///
    double share_zero mean_all mean_pre ///
    using `out_diag', replace

tempfile out_sizes
capture postclose handle_sizes
postfile handle_sizes ///
    str16 sample_tag ///
    str24 spec_tag ///
    double n_obs n_firms ///
    using `out_sizes', replace

// 6) Outcome list (new asks focus on levels + quantile bins + prior-significant outcomes)
// - cb_raised_usd        : dollars, includes zeros (paired with pos-only restrictions)
// - cb_log_raised_usd    : log dollars, drops zeros (intensive margin)
// - cb_any_raised        : 1{USD>0} extensive margin
// - cb_raised_usd_q100   : within-half-year percentile bin (1..100) of USD raised (xtile/q100)
// - cb_log1p_raised_usd  : log(1+USD raised) (prior significant)
// - cb_seriesAplus_round : indicator for A+ round in half-year (prior significant)
// - cb_seriesAplus_cum   : ever A+ by half-year (prior significant)
// - cb_log1p_cum_raised_usd : log(1+cum USD raised) (prior significant)
local outcomes ///
    cb_raised_usd ///
    cb_log_raised_usd ///
    cb_any_raised ///
    cb_raised_usd_q100 ///
    cb_log1p_raised_usd ///
    cb_seriesAplus_round ///
    cb_seriesAplus_cum ///
    cb_log1p_cum_raised_usd

// 7) Helper: run the canonical single-endog spec (var3, instrumented by var6)
program define __run_single_endog
    syntax, SAMPLE(string) SPEC(string) OUTCOME(name)

    local sample_tag "`sample'"
    local spec_tag "`spec'"
    local y "`outcome'"

    // Skip if empty or constant outcome
    quietly count if !missing(`y')
    if r(N) == 0 exit
    quietly summarize `y'
    if r(sd) == 0 exit

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
    reghdfe `y' var3, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
    local N = e(N)
    foreach p in var3 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_reg ("`sample_tag'") ("`spec_tag'") ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (.) (`N')
    }

    // IV
    ivreghdfe `y' (var3 = var6), absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst
    local rkf = e(rkf)
    local N = e(N)
    matrix FS = e(first)
    local F3 = FS[4,1]

    foreach p in var3 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        local pF = .
        if "`p'" == "var3" local pF = `F3'
        post handle_reg ("`sample_tag'") ("`spec_tag'") ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`pF') (`N')
    }

    // First stage (var3)
    estimates restore _ivreg2_var3
    local N_fs = e(N)
    foreach z in var6 {
        local b    = _b[`z']
        local se   = _se[`z']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("`sample_tag'") ("`spec_tag'") ("`y'") ("var3") ("`z'") ///
            (`b') (`se') (`pval') ///
            (`F3') (`rkf') (`N_fs')
    }
end

// Helper: post dataset-level sample sizes for current restriction
program define __post_size
    syntax, SAMPLE(string) SPEC(string)
    quietly count
    local n_obs = r(N)
    bys firm_id_num: gen byte __firm_tag = (_n == 1)
    quietly count if __firm_tag
    local n_firms = r(N)
    drop __firm_tag
    post handle_sizes ("`sample'") ("`spec'") (`n_obs') (`n_firms')
end

// Helper: post outcome diagnostics for current restriction
program define __post_diag
    syntax, SAMPLE(string) SPEC(string) OUTCOME(name)
    local y "`outcome'"
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

    post handle_diag ("`sample'") ("`spec'") ("`y'") ///
        (`n_total') (`n_nonmiss') (`n_missing') ///
        (`share_zero') (`mean_all') (`mean_pre')
end

// 8) Main loop: age restrictions × zeros policy ------------------------
local sample_tag "matched_private"
foreach age_cut in . 10 20 {
    foreach zeros in all pos {
        use `base', clear

        // Apply age restriction if requested
        if `age_cut' < . {
            keep if age < `age_cut'
        }

        // Apply zeros policy
        if "`zeros'" == "pos" {
            keep if cb_raised_usd > 0
        }

        // Spec tag label (keeps columns stable for later summaries)
        local spec_tag "baseline"
        if `age_cut' < . local spec_tag "age_lt`age_cut'"
        if "`zeros'" == "pos" local spec_tag "`spec_tag'_pos_usd_only"

        // Build outcomes needed for this snapshot
        capture drop cb_any_raised cb_log_raised_usd
        gen byte cb_any_raised = (cb_raised_usd > 0) if !missing(cb_raised_usd)
        gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0

        // Percentile rank should be computed within the analysis sample (by half-year).
        //
        // Use xtile-based q100 bins (1..100) rather than the continuous [0,1] rank.
        // Stata's xtile command cannot be combined with a by: prefix, so we use egen's xtile().
        capture drop cb_raised_usd_q100
        bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
        label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

        __post_size, sample("`sample_tag'") spec("`spec_tag'")

        // Diagnostics first (helps interpret magnitudes even if some outcomes drop)
        foreach y of local outcomes {
            __post_diag, sample("`sample_tag'") spec("`spec_tag'") outcome(`y')
        }

        // Regressions
        foreach y of local outcomes {
            __run_single_endog, sample("`sample_tag'") spec("`spec_tag'") outcome(`y')
        }
    }
}

// 8b) Geography columns: HQ in CA/NY vs HQ outside CA/NY (drop sample)
//
// These are *additional* sample restrictions requested as robustness checks,
// but we keep them as separate spec tags (columns) rather than a separate table.
//
// - hq_ca_ny: restrict sample to firms headquartered in CA or NY
// - hq_outside_ca_ny: restrict sample to firms headquartered outside CA/NY

// Drop-sample method: HQ in CA/NY (no age restriction; keep zeros)
use `base', clear
capture drop __hqstate hq_ca_ny
gen str8 __hqstate = upper(strtrim(hqstate))
gen byte hq_ca_ny = inlist(__hqstate, "CA", "NY")
keep if hq_ca_ny == 1
drop __hqstate hq_ca_ny

local spec_tag "hq_ca_ny"

capture drop cb_any_raised cb_log_raised_usd
gen byte cb_any_raised = (cb_raised_usd > 0) if !missing(cb_raised_usd)
gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0

capture drop cb_raised_usd_q100
bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

__post_size, sample("`sample_tag'") spec("`spec_tag'")
foreach y of local outcomes {
    __post_diag, sample("`sample_tag'") spec("`spec_tag'") outcome(`y')
}
foreach y of local outcomes {
    __run_single_endog, sample("`sample_tag'") spec("`spec_tag'") outcome(`y')
}

// Drop-sample method: outside CA/NY only (no age restriction; keep zeros)
use `base', clear
capture drop __hqstate hq_ca_ny
gen str8 __hqstate = upper(strtrim(hqstate))
gen byte hq_ca_ny = inlist(__hqstate, "CA", "NY")
keep if hq_ca_ny == 0
drop __hqstate hq_ca_ny

local spec_tag "hq_outside_ca_ny"

capture drop cb_any_raised cb_log_raised_usd
gen byte cb_any_raised = (cb_raised_usd > 0) if !missing(cb_raised_usd)
gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0

capture drop cb_raised_usd_q100
bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

__post_size, sample("`sample_tag'") spec("`spec_tag'")
foreach y of local outcomes {
    __post_diag, sample("`sample_tag'") spec("`spec_tag'") outcome(`y')
}
foreach y of local outcomes {
    __run_single_endog, sample("`sample_tag'") spec("`spec_tag'") outcome(`y')
}

// 9) Export ------------------------------------------------------------
postclose handle_reg
use `out_reg', clear
export delimited using "`out_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`out_dir'/first_stage.csv", replace delimiter(",") quote

postclose handle_diag
use `out_diag', clear
export delimited using "`out_dir'/outcome_diagnostics.csv", replace delimiter(",") quote

postclose handle_sizes
use `out_sizes', clear
export delimited using "`out_dir'/sample_sizes.csv", replace delimiter(",") quote

di as result "→ Wrote: `out_dir'/consolidated_results.csv"
di as result "→ Wrote: `out_dir'/first_stage.csv"
di as result "→ Wrote: `out_dir'/outcome_diagnostics.csv"
di as result "→ Wrote: `out_dir'/sample_sizes.csv"

log close _all
