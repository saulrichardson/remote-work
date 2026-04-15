*============================================================*
* firm_scaling_crunchbase_fundraising_prepost.do
*
* PI follow-up: collapse fundraising dollars into a single pre vs post comparison.
*
* Motivation (from transcript)
*   "Just pre post... add up all the money raised pre, all the money raised post...
*    no half-year controls... still a firm fixed effect."
*
* What this file does
*   1) Start from the matched-private Crunchbase panel (firm×half-year):
*        data/clean/firm_panel_with_cb_funding.csv
*   2) Collapse to firm×{pre,post} by summing USD raised across half-years.
*   3) Estimate the "pure" remote×post effect (drops Startup×Post):
*        y_iτ = β * (Remote×Post)_iτ + α_i + δ_τ + e_iτ
*      IV: (Remote×Post) instrumented by (Teleworkable×Post).
*
* Notes / design choices
*   - We keep firm FE and a single pre/post (covid) time FE.
*   - We use the *mean* of var3/var6 within period so this still works if
*     remote status varies within the post window.
*   - Outcomes are in levels (USD); we also report an average-per-half-year
*     outcome as a scale-normalized check.
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_prepost/
*     consolidated_results.csv
*     first_stage.csv
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

local specname "firm_scaling_crunchbase_fundraising_prepost"
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
    cb_raised_usd ///
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
    cb_raised_usd ///
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

// Ensure yh_num is numeric %th (even though we collapse, we use it for counts)
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

// 4) Baseline sample policy: Crunchbase-matched and drop public
keep if cb_matched == 1
keep if public != 1

// Guardrail: matched rows should use explicit zeros (not missing)
count if missing(cb_raised_usd)
if r(N) > 0 {
    di as error "Found " r(N) " matched row(s) with missing cb_raised_usd (should be 0)."
    exit 459
}

// 5) Collapse to firm×{pre,post}
// Count half-years per firm×period so we can build an average-per-half-year outcome.
preserve
    // Using (count) on yh_num yields # non-missing half-years in each period.
    collapse ///
        (sum)  cb_sum_raised_usd = cb_raised_usd ///
        (count) n_halfyears = yh_num ///
        (mean) var3 var6 ///
        , by(firm_id_num covid)

    // Scale-normalised outcome: average dollars per half-year in the period.
    gen double cb_avg_raised_usd = cb_sum_raised_usd / n_halfyears if n_halfyears > 0

    // 6) Output dirs + postfiles
    local out_dir "$results/`specname'"
    capture mkdir "`out_dir'"

    tempfile out_reg
    capture postclose handle_reg
    postfile handle_reg ///
        str16  sample_tag ///
        str32  outcome ///
        str8   model_type ///
        str16  param ///
        double coef se pval pre_mean ///
        double rkf partialF nobs ///
        using `out_reg', replace

    tempfile out_fs
    capture postclose handle_fs
    postfile handle_fs ///
        str16  sample_tag ///
        str32  outcome ///
        str16  endovar ///
        str16  param ///
        double coef se pval ///
        double partialF rkf nobs ///
        using `out_fs', replace

    tempfile out_sizes
    capture postclose handle_sizes
    postfile handle_sizes ///
        str16 sample_tag ///
        double n_obs n_firms ///
        using `out_sizes', replace

    // One sample in this collapsed setup: matched-private.
    local sample_tag "matched_private"

    // Post sample sizes (avoid nested preserve/restore)
    quietly count
    local n_obs = r(N)
    bys firm_id_num: gen byte __firm_tag = (_n == 1)
    quietly count if __firm_tag
    local n_firms = r(N)
    drop __firm_tag
    post handle_sizes ("`sample_tag'") (`n_obs') (`n_firms')

    // Outcomes to run (levels)
    local outcomes cb_sum_raised_usd cb_avg_raised_usd

    foreach y of local outcomes {
        quietly count if !missing(`y')
        if r(N) == 0 continue

        quietly summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        // OLS: firm FE + (pre/post) time FE
            reghdfe `y' var3, absorb(firm_id_num covid) vce(cluster firm_id_num)
            local N = e(N)
            foreach p in var3 {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_reg ("`sample_tag'") ("`y'") ("OLS") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (.) (`N')
            }

        // IV: var3 instrumented by var6 (pure spec: no var4 control)
        ivreghdfe `y' (var3 = var6), absorb(firm_id_num covid) vce(cluster firm_id_num) savefirst
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
            post handle_reg ("`sample_tag'") ("`y'") ("IV") ("`p'") ///
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
            post handle_fs ("`sample_tag'") ("`y'") ("var3") ("`z'") ///
                (`b') (`se') (`pval') ///
                (`F3') (`rkf') (`N_fs')
        }
    }

    // Export
    postclose handle_reg
    use `out_reg', clear
    export delimited using "`out_dir'/consolidated_results.csv", replace delimiter(",") quote

    postclose handle_fs
    use `out_fs', clear
    export delimited using "`out_dir'/first_stage.csv", replace delimiter(",") quote

    postclose handle_sizes
    use `out_sizes', clear
    export delimited using "`out_dir'/sample_sizes.csv", replace delimiter(",") quote

    di as result "→ Wrote: `out_dir'/consolidated_results.csv"
    di as result "→ Wrote: `out_dir'/first_stage.csv"
    di as result "→ Wrote: `out_dir'/sample_sizes.csv"
restore

log close _all
