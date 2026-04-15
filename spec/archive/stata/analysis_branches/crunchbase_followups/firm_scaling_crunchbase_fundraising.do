*============================================================*
* firm_scaling_crunchbase_fundraising.do
*
* Canonical Crunchbase fundraising spec (post-suite decision)
* ----------------------------------------------------------
* Goal:
*   Estimate the firm FE + time FE "remote × post" effect on Crunchbase
*   fundraising outcomes, using the same core RHS bundle as firm_scaling:
*
*     y = beta * (Remote × Post) + gamma * (Startup × Post) + FE_firm + FE_time + e
*
*   and instrument Remote × Post with Teleworkable × Post:
*     (Remote × Post)  <-  (Teleworkable × Post)
*
* Sample policy (PI):
*   - Restrict to Crunchbase-matched firms (cb_matched==1).
*   - Drop public firms (public==1) in the baseline (fundraising differs).
*   - Do NOT restrict to startup-only as main (report as robustness).
*   - Track match types and zero/missing behavior for each outcome.
*
* Outcomes (half-year):
*   - cb_any_round, cb_round_count
*   - cb_gt1_round, cb_gt2_round (repeat fundraising)
*   - cb_log1p_raised_usd (keeps zeros)
*   - cb_log_raised_usd (drops zeros; selected-sample robustness only)
*   - cb_raised_usd_q100 (within-half-year percentile bin; q100-style, matches user productivity scale)
*   - cb_rank_raised_yh (within-half-year percentile rank on [0,1]; skew-robust, behind-the-scenes check)
* Additional outcomes (available in builder output; shown in an appendix table):
*   - cb_seriesAplus_round (indicator: any Series A+ round in half-year)
*   - cb_seriesAplus_cum (indicator: ever reached Series A+ by half-year)
*   - cb_log1p_cum_raised_usd (robustness: cumulative dollars)
*
* Input:
*   data/clean/firm_panel_with_cb_funding.csv
*     (built by python src/py/build_firm_scaling_crunchbase_outcomes.py)
*
* Outputs:
*   results/raw/firm_scaling_crunchbase_fundraising/
*     consolidated_results.csv
*     first_stage.csv
*     outcome_diagnostics.csv
*     match_type_by_sample.csv
*============================================================*

// Optional arguments:
//   do spec/stata/firm_scaling_crunchbase_fundraising.do pure
//     -> runs the "Remote×Post only" version (drops Startup×Post control var4)
//   do spec/stata/firm_scaling_crunchbase_fundraising.do canonical 10
//     -> restricts to firms with age < 10 (age as-of 2020 in this pipeline)
args spec_variant age_max
local spec_variant = lower("`spec_variant'")
if "`spec_variant'" == "" local spec_variant "canonical"
if !inlist("`spec_variant'","canonical","pure","triple") {
    di as error "Unknown spec variant: `spec_variant' (expected: canonical|pure|triple)"
    exit 198
}

// Optional firm-age restriction
local age_restrict = 0
local age_max_num = .
if "`age_max'" != "" {
    local age_max_num = real("`age_max'")
    if `age_max_num' >= . {
        di as error "age_max must be numeric (e.g., 10 or 20). Got: `age_max'"
        exit 198
    }
    local age_restrict = 1
}

// Spec variants:
//   canonical : y ~ var3 + var4 + firm FE + time FE      (IV: var3 <- var6)
//   pure      : y ~ var3 + firm FE + time FE            (IV: var3 <- var6)
//   triple    : y ~ var3 + var5 + var4 + firm FE + time FE (IV: var3,var5 <- var6,var7)
local rhs_ols "var3"
local iv_syntax "(var3 = var6)"
local params_to_post "var3"
local fs_params "var6"
local is_triple = 0
if "`spec_variant'" == "canonical" {
    local rhs_ols "var3 var4"
    local iv_syntax "(var3 = var6) var4"
    local params_to_post "var3 var4"
    local fs_params "var6 var4"
}
else if "`spec_variant'" == "pure" {
    // keep defaults (var3 only)
}
else if "`spec_variant'" == "triple" {
    local is_triple = 1
    local rhs_ols "var3 var5 var4"
    local iv_syntax "(var3 var5 = var6 var7) var4"
    local params_to_post "var3 var5 var4"
    local fs_params "var6 var7 var4"
}

// 0) Bootstrap paths + logging
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

local specname "firm_scaling_crunchbase_fundraising"
if "`spec_variant'" != "canonical" {
    local specname "`specname'_`spec_variant'"
}
if `age_restrict' {
    // Keep output dirs distinct across age cutoffs
    local specname "`specname'_age_lt`age_max'"
}
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

// Preserve case so that variable names match the CSV header exactly
// (notably: cb_seriesAplus_round / cb_seriesAplus_cum).
import delimited using "`in_csv'", clear varnames(1) case(preserve) stringcols(_all)

// 2) Required variables
local required_vars ///
    firm_id yh_num covid startup remote teleworkable ///
    var3 var4 var6 ///
    cb_matched cb_round_count cb_any_round cb_raised_usd ///
    cb_seriesAplus_round cb_seriesAplus_cum ///
    cb_log1p_cum_raised_usd ///
    public match_type
if `is_triple' {
    local required_vars "`required_vars' var5 var7"
}

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

// 3) Variable hygiene: destring numeric columns (CB + core RHS + IDs)
local maybe_numeric ///
    firm_id yh_num yh ///
    covid startup remote teleworkable ///
    var3 var4 var5 var6 var7 ///
    cb_matched cb_round_count cb_any_round cb_raised_usd cb_log1p_raised_usd ///
    cb_cum_raised_usd cb_log1p_cum_raised_usd cb_dlog_cum_raised cb_dlog_cum_raised_we ///
    cb_seriesAplus_round cb_seriesAplus_cum ///
    public age

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

// 4) Restrict to Crunchbase-matched rows; enforce "missing != zero" semantics.
keep if cb_matched == 1

// Optional firm-age restriction (applied after match restriction so age applies
// to the analysis firms, not unmatched placeholders).
if `age_restrict' {
    capture confirm variable age
    if _rc {
        di as error "Requested age restriction but 'age' is missing from `in_csv'."
        exit 198
    }
    capture confirm numeric variable age
    if _rc {
        destring age, replace ignore(" ,")
    }
    keep if age < `age_max_num'
}

count if missing(cb_round_count)
if r(N) > 0 {
    di as error "Found " r(N) " matched row(s) with missing cb_round_count."
    di as error "This indicates Crunchbase outcomes were not filled as 0 for matched firms."
    exit 459
}
count if missing(cb_raised_usd)
if r(N) > 0 {
    di as error "Found " r(N) " matched row(s) with missing cb_raised_usd."
    exit 459
}

// Construct outcomes if missing from builder (guardrail).
capture confirm variable cb_any_round
if _rc {
    gen byte cb_any_round = (cb_round_count > 0) if !missing(cb_round_count)
}
capture confirm variable cb_log1p_raised_usd
if _rc {
    gen double cb_log1p_raised_usd = ln(1 + cb_raised_usd) if !missing(cb_raised_usd)
}

gen byte cb_gt1_round = (cb_round_count > 1) if !missing(cb_round_count)
gen byte cb_gt2_round = (cb_round_count > 2) if !missing(cb_round_count)
gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0

label var cb_any_round "1{Any CB funding round in half-year}"
label var cb_round_count "# CB funding rounds in half-year"
label var cb_gt1_round "1{CB rounds > 1} in half-year"
label var cb_gt2_round "1{CB rounds > 2} in half-year"
label var cb_log1p_raised_usd "log(1+USD raised) in half-year"
label var cb_log_raised_usd "log(USD raised) in half-year (drops zeros)"
label var cb_seriesAplus_round "1{Any Series A+ round in half-year}"
label var cb_seriesAplus_cum "1{Ever reached Series A+ by half-year}"
label var cb_log1p_cum_raised_usd "log(1+cumulative USD raised)"

// 5) Output directories + postfiles
local out_dir "$results/`specname'"
capture mkdir "`out_dir'"

tempfile out_reg
capture postclose handle_reg
postfile handle_reg ///
    str24 sample_tag ///
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

tempfile out_match
capture postclose handle_match
postfile handle_match ///
    str24 sample_tag ///
    str20 match_type ///
    double firms ///
    using `out_match', replace

// Percentiles for skew diagnostics (requested by PI).
tempfile out_pctl
capture postclose handle_pctl
postfile handle_pctl ///
    str24 sample_tag ///
    str32 outcome ///
    double n_nonmiss ///
    double p50 p75 p90 p95 p99 max ///
    using `out_pctl', replace

// 6) Define outcome list (run all in every sample)
local outcomes ///
//     cb_round_count ///
//     cb_any_round ///
//     cb_gt1_round ///
//     cb_gt2_round ///
//     cb_seriesAplus_round ///
    cb_log1p_raised_usd ///
//     cb_raised_usd_q100 ///
//     cb_log_raised_usd ///
//     cb_rank_raised_yh ///
//     cb_seriesAplus_cum ///
//     cb_log1p_cum_raised_usd

// 7) Samples (baseline + robustness)
//   private      : cb_matched==1 and public==0 (main)
//   startup      : private, plus startup==1 (robustness; lower N)
//   no_name_only : private, drop match_type=="name_only" (match-quality robustness)
local sample_tags "private startup no_name_only"
if `is_triple' {
    // In the startup-only sample, var5 == var3 (collinear), so the triple spec is unidentified.
    local sample_tags "private no_name_only"
}

foreach s of local sample_tags {
    preserve

        // Baseline restriction: drop public firms
        keep if public != 1

        if "`s'" == "startup" {
            keep if startup == 1
        }
        else if "`s'" == "no_name_only" {
            drop if match_type == "name_only"
        }
        else if "`s'" != "private" {
            di as error "Unknown sample tag: `s'"
            exit 198
        }

        // Rank outcome should be computed within the analysis sample.
        capture drop cb_rank_raised_yh cb_raised_usd_q100 __rankN_yh

        // q100-style rank (matches user productivity q100 scale): 1..100 within half-year.
        // Stata's xtile command cannot be combined with a by: prefix, so we use egen's xtile()
        // within half-year. This is still a within-half-year 100-quantile bin assignment.
        bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
        label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

        // Continuous percentile rank on [0,1] (skew-robust; behind-the-scenes check).
        bys yh_num: egen double cb_rank_raised_yh = rank(cb_raised_usd) if !missing(cb_raised_usd)
        bys yh_num: egen long   __rankN_yh = count(cb_raised_usd) if !missing(cb_raised_usd)
        replace cb_rank_raised_yh = (cb_rank_raised_yh - 1) / (__rankN_yh - 1) if __rankN_yh > 1
        drop __rankN_yh
        label var cb_rank_raised_yh "Within-half-year percentile rank of USD raised"

        // Match type distribution (unique firms)
        tempfile _sample
        save `_sample', replace
        keep firm_id_num match_type
        duplicates drop
        // Avoid missing() ambiguity on string vars: treat blank as missing explicitly.
        replace match_type = "missing" if match_type == ""
        contract match_type, freq(firms)
        forvalues i = 1/`=_N' {
            post handle_match ("`s'") (match_type[`i']) (firms[`i'])
        }
        use `_sample', clear

        // Outcome diagnostics (N / zeros / means)
        foreach y of local outcomes {
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

        // Skew diagnostics: percentiles for key money outcomes.
        // (We keep these in a separate CSV; not shown in the main PDF by default.)
        local pctl_outcomes "cb_raised_usd cb_log1p_raised_usd cb_cum_raised_usd cb_log1p_cum_raised_usd cb_log_raised_usd"
        foreach y of local pctl_outcomes {
            capture confirm variable `y'
            if _rc continue

            quietly count if !missing(`y')
            local n_nonmiss = r(N)
            if `n_nonmiss' == 0 continue

            quietly summarize `y', detail
            post handle_pctl ("`s'") ("`y'") ///
                (`n_nonmiss') ///
                (r(p50)) (r(p75)) (r(p90)) (r(p95)) (r(p99)) (r(max))
        }

        // Main regressions: firm FE + time FE; remote and post are absorbed.
        // By default we keep startup×post (var4) as a control but DO NOT include the triple interaction.
        // "pure" variant drops var4 so the only regressor is Remote×Post (var3).
        foreach y of local outcomes {
            quietly count if !missing(`y')
            if r(N) == 0 {
                di as text "Skipping `y' in sample `s' (no non-missing observations)."
                continue
            }

            quietly summarize `y' if covid == 0, meanonly
            local pre_mean = r(mean)

            // OLS
            reghdfe `y' `rhs_ols', absorb(firm_id_num yh_num) vce(cluster firm_id_num)
            local N = e(N)
            foreach p of local params_to_post {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_reg ("`s'") ("OLS") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (.) (`N')
            }

            // IV
            //   canonical/pure: instrument Remote×Post (var3) with Teleworkable×Post (var6)
            //   triple        : instrument (var3,var5) with (var6,var7)
            ivreghdfe `y' `iv_syntax', absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst
            local rkf = e(rkf)
            local N = e(N)
            matrix FS = e(first)
            local F3 = FS[4,1]
            local F5 = .
            if `is_triple' {
                local F5 = FS[4,2]
            }

            foreach p of local params_to_post {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                local pF = .
                if "`p'" == "var3" local pF = `F3'
                if "`p'" == "var5" local pF = `F5'
                post handle_reg ("`s'") ("IV") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`pF') (`N')
            }

            // First stage(s)
            //  - canonical/pure: var3 only
            //  - triple        : var3 and var5
            estimates restore _ivreg2_var3
            local N_fs = e(N)
            foreach p of local fs_params {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_fs ("`s'") ("`y'") ("var3") ("`p'") ///
                    (`b') (`se') (`pval') ///
                    (`F3') (`rkf') (`N_fs')
            }

            if `is_triple' {
                estimates restore _ivreg2_var5
                local N_fs = e(N)
                foreach p of local fs_params {
                    local b    = _b[`p']
                    local se   = _se[`p']
                    local t    = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    post handle_fs ("`s'") ("`y'") ("var5") ("`p'") ///
                        (`b') (`se') (`pval') ///
                        (`F5') (`rkf') (`N_fs')
                }
            }
        }

    restore
}



// 8) Export results
postclose handle_reg
use `out_reg', clear
export delimited using "`out_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`out_dir'/first_stage.csv", replace delimiter(",") quote

postclose handle_diag
use `out_diag', clear
export delimited using "`out_dir'/outcome_diagnostics.csv", replace delimiter(",") quote

postclose handle_match
use `out_match', clear
export delimited using "`out_dir'/match_type_by_sample.csv", replace delimiter(",") quote

postclose handle_pctl
use `out_pctl', clear
export delimited using "`out_dir'/outcome_percentiles.csv", replace delimiter(",") quote

di as result "→ Wrote: `out_dir'/consolidated_results.csv"
di as result "→ Wrote: `out_dir'/first_stage.csv"
di as result "→ Wrote: `out_dir'/outcome_diagnostics.csv"
di as result "→ Wrote: `out_dir'/match_type_by_sample.csv"
di as result "→ Wrote: `out_dir'/outcome_percentiles.csv"

log close _all
