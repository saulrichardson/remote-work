*============================================================*
* firm_scaling_crunchbase_fundraising_cohort_fe.do
*
* Purpose
*   Test alternative cohort-based fixed effect approaches for the
*   Crunchbase fundraising regressions, with a focus on *removing startup*
*   from the RHS while controlling flexibly for founding-year cohort patterns.
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_cohort_fe/
*     consolidated_results.csv
*     first_stage.csv
*
* Notes
*   - Baseline sample policy mirrors the canonical fundraising table:
*       keep if cb_matched==1 and public!=1
*   - We record only the coefficient on var3 (Remote×Post) for comparability
*     across FE/control variants.
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

local specname "firm_scaling_crunchbase_fundraising_cohort_fe"
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
    firm_id yh_num covid remote teleworkable ///
    var3 var6 ///
    cb_matched public founded ///
    cb_round_count cb_raised_usd cb_log1p_raised_usd ///
    cb_seriesAplus_round cb_seriesAplus_cum cb_log1p_cum_raised_usd

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

// 3) Variable hygiene: destring numeric columns we will use
local maybe_numeric ///
    yh_num covid remote teleworkable ///
    var3 var4 var5 var6 var7 ///
    cb_matched cb_round_count cb_raised_usd cb_log1p_raised_usd ///
    cb_seriesAplus_round cb_seriesAplus_cum cb_log1p_cum_raised_usd ///
    public founded

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

// 4) Baseline sample policy (canonical fundraising table)
keep if cb_matched == 1
keep if public != 1

// Guardrail: matched rows should use explicit zeros (not missing)
count if missing(cb_round_count)
if r(N) > 0 {
    di as error "Found " r(N) " matched row(s) with missing cb_round_count (should be 0)."
    exit 459
}
count if missing(cb_raised_usd)
if r(N) > 0 {
    di as error "Found " r(N) " matched row(s) with missing cb_raised_usd (should be 0)."
    exit 459
}

// 5) Derived outcomes (match canonical semantics)
// NOTE: input CSV is imported with stringcols(_all), so cb_* may arrive as strings.
// We explicitly (re)construct these outcomes from cb_round_count to guarantee numeric type.
capture drop cb_any_round
capture drop cb_gt1_round
capture drop cb_gt2_round
gen byte cb_any_round = (cb_round_count > 0) if !missing(cb_round_count)
gen byte cb_gt1_round = (cb_round_count > 1) if !missing(cb_round_count)
gen byte cb_gt2_round = (cb_round_count > 2) if !missing(cb_round_count)

// Within-half-year percentile bin (1..100) of USD raised, q100-style.
// This is *not* a uniform percentile because cb_raised_usd has mass at zero.
capture drop cb_raised_usd_q100
bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)

// Positive-only log dollars (intensive margin)
capture drop cb_log_raised_usd
gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0

// Founding-year cohorts
capture drop cohort cohort5 year
gen int cohort = floor(founded)
gen int cohort5 = floor(cohort/5)*5
gen int year = year(dofh(yh_num))

// 6) Define outcome list
local outcomes ///
    cb_round_count ///
    cb_any_round ///
    cb_gt1_round ///
    cb_gt2_round ///
    cb_seriesAplus_round ///
    cb_seriesAplus_cum ///
    cb_log1p_raised_usd ///
    cb_log1p_cum_raised_usd ///
    cb_raised_usd_q100 ///
    cb_log_raised_usd

// 7) Output dir + postfiles
local out_dir "$results/`specname'"
capture mkdir "`out_dir'"

tempfile out_reg
capture postclose handle_reg
postfile handle_reg ///
    str28 spec_tag ///
    str8  model_type ///
    str32 outcome ///
    str12 param ///
    double coef se pval pre_mean ///
    double rkf partialF nobs ///
    using `out_reg', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str28 spec_tag ///
    str32 outcome ///
    str8  endovar ///
    str12 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

// 8) Spec variants to test
// All variants post the effect of var3 (Remote×Post), instrumented by var6 (Teleworkable×Post).
local spec_tags ///
    pure_yh_fe ///
    cohort_linear_post ///
    cohortXpost_fe ///
    cohortXyear_fe ///
    cohort5Xyear_fe ///
    cohortXyear_plus_yh_fe ///
    cohort5Xyear_plus_yh_fe ///
    cohortXhalfyear_fe

foreach sp of local spec_tags {
    preserve

        // Default: baseline (pure var3, firm FE + half-year FE)
        local rhs_ols "var3"
        local iv_syntax "(var3 = var6)"
        local absorb_opts "firm_id_num yh_num"

        if "`sp'" == "pure_yh_fe" {
            // keep defaults
        }
        else if "`sp'" == "cohort_linear_post" {
            // Linear cohort×post shift (robustness-style control)
            capture drop founded_post
            gen double founded_post = (cohort - 2000) * covid
            local rhs_ols "var3 founded_post"
            local iv_syntax "(var3 = var6) founded_post"
        }
        else if "`sp'" == "cohortXpost_fe" {
            // Cohort×Post fixed effects (founding-year cohort interacted with Post),
            // implemented as an absorbed FE to keep IV machinery stable.
            local absorb_opts "firm_id_num yh_num cohort#covid"
        }
        else if "`sp'" == "cohortXyear_fe" {
            // Cohort×calendar-year fixed effects (absorb cohort×year)
            local absorb_opts "firm_id_num cohort#year"
        }
        else if "`sp'" == "cohort5Xyear_fe" {
            // Binned cohort (5-year) × calendar-year fixed effects
            local absorb_opts "firm_id_num cohort5#year"
        }
        else if "`sp'" == "cohortXyear_plus_yh_fe" {
            // Cohort×calendar-year FE PLUS half-year FE.
            // This keeps the baseline half-year time shocks while allowing cohort-specific year shifts.
            local absorb_opts "firm_id_num yh_num cohort#year"
        }
        else if "`sp'" == "cohort5Xyear_plus_yh_fe" {
            // 5-year binned cohort×calendar-year FE PLUS half-year FE.
            local absorb_opts "firm_id_num yh_num cohort5#year"
        }
        else if "`sp'" == "cohortXhalfyear_fe" {
            // Cohort×half-year fixed effects (most flexible)
            local absorb_opts "firm_id_num cohort#yh_num"
        }
        else {
            di as error "Unknown spec tag: `sp'"
            exit 198
        }

        foreach y of local outcomes {

            // Skip outcomes with no data under this spec's sample (e.g., log positive-only)
            quietly count if !missing(`y')
            if r(N) == 0 {
                di as text "Skipping `y' under `sp' (no non-missing observations)."
                continue
            }

            quietly summarize `y' if covid == 0, meanonly
            local pre_mean = r(mean)

            // ------------------------- OLS --------------------------
            capture noisily reghdfe `y' `rhs_ols', absorb(`absorb_opts') vce(cluster firm_id_num)
            if _rc {
                di as error "OLS failed for outcome=`y' spec=`sp' (rc=" _rc ")."
                continue
            }
            local N = e(N)
            local b = _b[var3]
            local se = _se[var3]
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_reg ("`sp'") ("OLS") ("`y'") ("var3") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (.) (`N')

            // -------------------------- IV --------------------------
            capture noisily ivreghdfe `y' `iv_syntax', absorb(`absorb_opts') vce(cluster firm_id_num) savefirst
            if _rc {
                di as error "IV failed for outcome=`y' spec=`sp' (rc=" _rc ")."
                continue
            }

            local rkf = e(rkf)
            local N = e(N)
            matrix FS = e(first)
            local F3 = FS[4,1]

            local b = _b[var3]
            local se = _se[var3]
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_reg ("`sp'") ("IV") ("`y'") ("var3") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`F3') (`N')

            // First-stage coefficient(s) for var3 equation
            capture estimates restore _ivreg2_var3
            if _rc == 0 {
                local N_fs = e(N)
                foreach z in var6 {
                    local bz = _b[`z']
                    local sez = _se[`z']
                    local tz = `bz'/`sez'
                    local pz = 2*ttail(e(df_r), abs(`tz'))
                    post handle_fs ("`sp'") ("`y'") ("var3") ("`z'") ///
                        (`bz') (`sez') (`pz') ///
                        (`F3') (`rkf') (`N_fs')
                }
            }
        }

    restore
}

// 9) Export
postclose handle_reg
use `out_reg', clear
export delimited using "`out_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`out_dir'/first_stage.csv", replace delimiter(",") quote

di as result "→ Wrote: `out_dir'/consolidated_results.csv"
di as result "→ Wrote: `out_dir'/first_stage.csv"
log close _all
