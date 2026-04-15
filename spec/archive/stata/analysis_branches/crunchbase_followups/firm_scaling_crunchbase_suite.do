*============================================================*
* firm_scaling_crunchbase_suite.do
*
* Purpose
*   Empirically test Crunchbase fundraising outcomes against the "remote × post"
*   firm FE + time FE spec, following PI diagnostics:
*     - Drop public firms first; compare to startup-only restriction
*     - Be explicit about missing vs zero and destring Crunchbase variables
*     - Run count/dummy/threshold/log/log1p/rank outcomes
*     - Track N, missing, zeros, and IV strength stats (first-stage F / rkf)
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*
* Outputs
*   results/raw/firm_scaling_crunchbase_suite/
*     regression_results.csv
*     first_stage_results.csv
*     outcome_diagnostics.csv
*     match_type_by_sample.csv
*============================================================*

// 0) Bootstrap paths
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

local specname "firm_scaling_crunchbase_suite"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

// Dependency checks (fail fast)
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

import delimited using "`in_csv'", clear stringcols(_all)

// 2) Required variables
local required_vars ///
    firm_id yh_num yh covid startup remote teleworkable ///
    var3 var4 var5 var6 var7 ///
    cb_matched cb_round_count cb_any_round cb_raised_usd cb_log1p_raised_usd ///
    public match_type

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

// 3) Variable hygiene: destring numeric columns (Crunchbase + key RHS)
local maybe_numeric ///
    yh yh_num firm_id cb_matched public startup covid ///
    remote teleworkable var3 var4 var5 var6 var7 ///
    cb_round_count cb_any_round cb_raised_usd cb_log1p_raised_usd ///
    cb_seriesAplus_round cb_seriesAplus_cum ///
    cb_cum_raised_usd cb_log1p_cum_raised_usd cb_dlog_cum_raised cb_dlog_cum_raised_we

foreach v of local maybe_numeric {
    capture confirm variable `v'
    if !_rc {
        capture confirm numeric variable `v'
        if _rc {
            destring `v', replace ignore(" ,")
        }
    }
}

// Convert half-year key to Stata %th numeric for fixed effects.
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

// Sanity: confirm Crunchbase outcomes are not silently missing for matched rows
count if cb_matched == 1 & missing(cb_round_count)
if r(N) > 0 {
    di as error "Found " r(N) " matched row(s) with missing cb_round_count."
    di as error "This suggests the builder did not fill zeros for matched firms."
    exit 459
}

// 4) Construct additional outcomes (thresholds, log(raised), rank robustness)
gen byte cb_gt1_round = (cb_round_count > 1) if !missing(cb_round_count)
label var cb_gt1_round "1{CB rounds > 1} in half-year"

gen byte cb_gt2_round = (cb_round_count > 2) if !missing(cb_round_count)
label var cb_gt2_round "1{CB rounds > 2} in half-year"

gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0
label var cb_log_raised_usd "log(USD raised) (drops zeros)"

// 5) Output directories + postfiles
local out_dir "$results/firm_scaling_crunchbase_suite"
capture mkdir "`out_dir'"

tempfile out_reg
capture postclose handle_reg
postfile handle_reg ///
    str24 sample_tag ///
    str24 spec_tag ///
    str8  model_type ///
    str32 outcome ///
    str12 param ///
    double coef se pval pre_mean ///
    double rkf partialF nobs ///
    using `out_reg', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str24 sample_tag ///
    str24 spec_tag ///
    str32 outcome ///
    str8  endovar ///
    str12 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

tempfile out_diag
capture postclose handle_diag
postfile handle_diag ///
    str24 sample_tag ///
    str32 outcome ///
    double n_total n_nonmiss n_missing ///
    double share_zero mean_all mean_pre ///
    using `out_diag', replace

// 6) Define test matrix
local outcomes ///
    cb_round_count ///
    cb_any_round ///
    cb_gt1_round ///
    cb_gt2_round ///
    cb_log1p_raised_usd ///
    cb_log_raised_usd ///
    cb_rank_raised_yh

// Spec variants:
//   simple      : y on var3 (remote×post), firm FE + time FE
//   startup_post: y on var3 + var4 (startup×post) as control
//   triple       : baseline-style var3 + var5 + var4 (remote×post×startup) with 2SLS (optional robustness)
local spec_tags "simple startup_post triple"

// Sample variants:
//   cb_matched      : cb_matched==1 (diagnostic only)
//   cb_private      : cb_matched==1 and public!=1 (PI baseline)
//   cb_private_start: cb_private plus startup==1 (robustness)
//   cb_private_direct: cb_private but restrict to direct_cb_url matches (robustness)
//   cb_private_no_name_only: cb_private but drop name_only matches (robustness)
local sample_tags "cb_matched cb_private cb_private_start cb_private_direct cb_private_no_name_only"

// 7) Match-type diagnostics by sample
tempfile match_diag
capture postclose handle_match
postfile handle_match ///
    str24 sample_tag ///
    str20 match_type ///
    double firms ///
    using `match_diag', replace

// 8) Main loop: samples × outcomes × spec variants
foreach s of local sample_tags {
    preserve

        // Apply sample restriction
        if "`s'" == "cb_matched" {
            keep if cb_matched == 1
        }
        else if "`s'" == "cb_private" {
            keep if cb_matched == 1
            // "public" sometimes imports as string; we already destringed above.
            drop if public == 1
        }
        else if "`s'" == "cb_private_start" {
            keep if cb_matched == 1
            drop if public == 1
            keep if startup == 1
        }
        else if "`s'" == "cb_private_direct" {
            keep if cb_matched == 1
            drop if public == 1
            keep if match_type == "direct_cb_url"
        }
        else if "`s'" == "cb_private_no_name_only" {
            keep if cb_matched == 1
            drop if public == 1
            drop if match_type == "name_only"
        }
        else {
            di as error "Unknown sample tag: `s'"
            exit 198
        }

        // Rank robustness outcome should be computed *within the analysis sample*
        // (so public-firm rows we drop do not affect the rank scale).
        capture drop cb_rank_raised_yh __rankN_yh
        bys yh_num: egen double cb_rank_raised_yh = rank(cb_raised_usd) if !missing(cb_raised_usd)
        bys yh_num: egen long   __rankN_yh = count(cb_raised_usd) if !missing(cb_raised_usd)
        replace cb_rank_raised_yh = (cb_rank_raised_yh - 1) / (__rankN_yh - 1) if __rankN_yh > 1
        drop __rankN_yh
        label var cb_rank_raised_yh "Within-half-year percentile rank of USD raised"

        // Match-type distribution (unique firms)
        // NOTE: preserve/restore cannot be nested, so we snapshot to a tempfile.
        tempfile _sample
        save `_sample', replace

        keep firm_id_num match_type
        duplicates drop
        replace match_type = "missing" if missing(match_type)
        contract match_type, freq(firms)
        forvalues i = 1/`=_N' {
            post handle_match ("`s'") (match_type[`i']) (firms[`i'])
        }
        use `_sample', clear

        // Outcome diagnostics (N / zeros / means)
        foreach y of local outcomes {
            capture confirm variable `y'
            if _rc {
                di as error "Missing outcome `y' (expected to exist after construction)."
                exit 198
            }

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

            post handle_diag ("`s'") ("`y'") ///
                (`n_total') (`n_nonmiss') (`n_missing') ///
                (`share_zero') (`mean_all') (`mean_pre')
        }

        // Regressions
        foreach y of local outcomes {
            // Skip if outcome has no data (e.g., log outcome if everything is zero)
            quietly count if !missing(`y')
            if r(N) == 0 {
                di as text "Skipping `y' in sample `s' (no non-missing observations)."
                continue
            }

            quietly summarize `y' if covid == 0, meanonly
            local pre_mean = r(mean)

            foreach sp of local spec_tags {
                // -------------------------
                // OLS
                // -------------------------
                if "`sp'" == "simple" {
                    reghdfe `y' var3, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
                    local N = e(N)
                    foreach p in var3 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        post handle_reg ("`s'") ("`sp'") ("OLS") ("`y'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (.) (.) (`N')
                    }

                    // IV: var3 instrumented by var6
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
                        post handle_reg ("`s'") ("`sp'") ("IV") ("`y'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (`rkf') (`F3') (`N')
                    }

                    // First stage coefficients
                    estimates restore _ivreg2_var3
                    local N_fs = e(N)
                    foreach p in var6 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        post handle_fs ("`s'") ("`sp'") ("`y'") ("var3") ("`p'") ///
                            (`b') (`se') (`pval') ///
                            (`F3') (`rkf') (`N_fs')
                    }
                }
                else if "`sp'" == "startup_post" {
                    reghdfe `y' var3 var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
                    local N = e(N)
                    foreach p in var3 var4 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        post handle_reg ("`s'") ("`sp'") ("OLS") ("`y'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (.) (.) (`N')
                    }

                    ivreghdfe `y' (var3 = var6) var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst
                    local rkf = e(rkf)
                    local N = e(N)
                    matrix FS = e(first)
                    local F3 = FS[4,1]

                    foreach p in var3 var4 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        local pF = .
                        if "`p'" == "var3" local pF = `F3'
                        post handle_reg ("`s'") ("`sp'") ("IV") ("`y'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (`rkf') (`pF') (`N')
                    }

                    estimates restore _ivreg2_var3
                    local N_fs = e(N)
                    foreach p in var6 var4 {
                        capture confirm variable `p'
                        if _rc continue
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        post handle_fs ("`s'") ("`sp'") ("`y'") ("var3") ("`p'") ///
                            (`b') (`se') (`pval') ///
                            (`F3') (`rkf') (`N_fs')
                    }
                }
                else if "`sp'" == "triple" {
                    // Baseline-style robustness: includes remote×post×startup (var5)
                    reghdfe `y' var3 var5 var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
                    local N = e(N)
                    foreach p in var3 var5 var4 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        post handle_reg ("`s'") ("`sp'") ("OLS") ("`y'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (.) (.) (`N')
                    }

                    ivreghdfe `y' (var3 var5 = var6 var7) var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst
                    local rkf = e(rkf)
                    local N = e(N)
                    matrix FS = e(first)
                    local F3 = FS[4,1]
                    local F5 = FS[4,2]

                    foreach p in var3 var5 var4 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        local pF = .
                        if "`p'" == "var3" local pF = `F3'
                        if "`p'" == "var5" local pF = `F5'
                        post handle_reg ("`s'") ("`sp'") ("IV") ("`y'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (`rkf') (`pF') (`N')
                    }

                    // First stages
                    estimates restore _ivreg2_var3
                    local N_fs = e(N)
                    foreach p in var6 var7 var4 {
                        local b    = _b[`p']
                        local se   = _se[`p']
                        local t    = `b'/`se'
                        local pval = 2*ttail(e(df_r), abs(`t'))
                        post handle_fs ("`s'") ("`sp'") ("`y'") ("var3") ("`p'") ///
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
                        post handle_fs ("`s'") ("`sp'") ("`y'") ("var5") ("`p'") ///
                            (`b') (`se') (`pval') ///
                            (`F5') (`rkf') (`N_fs')
                    }
                }
                else {
                    di as error "Unknown spec tag: `sp'"
                    exit 198
                }
            }
        }
    restore
}

// 9) Export suite outputs
postclose handle_reg
use `out_reg', clear
export delimited using "`out_dir'/regression_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`out_dir'/first_stage_results.csv", replace delimiter(",") quote

postclose handle_diag
use `out_diag', clear
export delimited using "`out_dir'/outcome_diagnostics.csv", replace delimiter(",") quote

postclose handle_match
use `match_diag', clear
export delimited using "`out_dir'/match_type_by_sample.csv", replace delimiter(",") quote

di as result "→ Wrote: `out_dir'/regression_results.csv"
di as result "→ Wrote: `out_dir'/first_stage_results.csv"
di as result "→ Wrote: `out_dir'/outcome_diagnostics.csv"
di as result "→ Wrote: `out_dir'/match_type_by_sample.csv"

log close _all
