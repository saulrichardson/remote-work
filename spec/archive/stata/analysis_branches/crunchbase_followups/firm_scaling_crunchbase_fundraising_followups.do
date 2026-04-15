*============================================================*
* firm_scaling_crunchbase_fundraising_followups.do
*
* Purpose
*   A single "meeting follow-ups" spec that runs the *canonical* Crunchbase
*   fundraising regression on a small set of targeted sample restrictions:
*
*     y = beta * (Remote × Post) + gamma * (Startup × Post) + FE_firm + FE_time + e
*     IV: (Remote × Post)  <-  (Teleworkable × Post)
*
*   This file is intentionally narrow: it exists to answer concrete questions
*   from transcript notes, without editing the canonical fundraising table spec.
*
* Empirical asks covered here
*   (2) Age restrictions in matched-private sample:
*         - Age < 10
*         - Age < 20
*   (4) Intensive margin (no-zeros) for dollars raised:
*         - Keep only firm×period rows with cb_raised_usd > 0
*   (5) Restrict to firms that ever raised at least one round:
*         - Keep only firms with max(cb_round_count) > 0 over the panel
*   (7) Geography mechanism checks:
*         - Separate regressions for HQ in NY/SF vs HQ outside NY/SF
*         - (Optional) interaction spec: Remote×Post×Outside(NY/SF), instrumented
*           by Teleworkable×Post×Outside(NY/SF)
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_followups/
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

local specname "firm_scaling_crunchbase_fundraising_followups"
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

// Preserve case so variable names match the CSV header exactly.
import delimited using "`in_csv'", clear varnames(1) case(preserve) stringcols(_all)

// 2) Required variables
local required_vars ///
    firm_id yh_num covid startup remote teleworkable ///
    var3 var4 var6 ///
    cb_matched cb_round_count cb_raised_usd cb_log1p_raised_usd ///
    public age hqcity hqstate

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

// 3) Variable hygiene: destring numeric columns
local maybe_numeric ///
    firm_id yh_num ///
    covid startup remote teleworkable ///
    var3 var4 var6 ///
    cb_matched cb_round_count cb_raised_usd cb_log1p_raised_usd ///
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

// 4) Enforce the "matched implies zeros filled" contract.
keep if cb_matched == 1
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

// Derived outcomes
capture drop cb_log_raised_usd
gen double cb_log_raised_usd = log(cb_raised_usd) if cb_raised_usd > 0
label var cb_log_raised_usd "log(USD raised), intensive margin (cb_raised_usd>0)"

// Firm-level "ever raised a round" indicator (uses cb_round_count, not dollars)
capture drop __any_round ever_round
gen byte __any_round = (cb_round_count > 0) if !missing(cb_round_count)
bys firm_id_num: egen byte ever_round = max(__any_round)
drop __any_round
label var ever_round "Firm ever has cb_round_count>0 (in sample window)"

// Geography indicator: HQ in (New York, NY) or (San Francisco, CA)
capture drop hq_ny_sf
gen strL __hqcity = lower(strtrim(hqcity))
gen str8 __hqstate = upper(strtrim(hqstate))
gen byte hq_ny_sf = .
replace hq_ny_sf = 1 if (__hqcity == "new york" & __hqstate == "NY")
replace hq_ny_sf = 1 if (__hqcity == "san francisco" & __hqstate == "CA")
replace hq_ny_sf = 0 if hq_ny_sf == . & __hqcity != "" & __hqstate != ""
drop __hqcity __hqstate
label var hq_ny_sf "HQ is New York, NY or San Francisco, CA"

// 5) Baseline policy: drop public firms (public as-of-today filter)
tempfile matched_all
save `matched_all', replace

tempfile matched_private
use `matched_all', clear
keep if public != 1
save `matched_private', replace

// 6) Regression runner
local out_dir "$results/`specname'"
capture mkdir "`out_dir'"

tempfile out_reg
capture postclose handle_reg
postfile handle_reg ///
    str32 sample_tag ///
    str16 spec_tag ///
    str8  model_type ///
    str32 outcome ///
    str16 param ///
    double coef se pval pre_mean ///
    double rkf partialF nobs ///
    using `out_reg', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str32 sample_tag ///
    str16 spec_tag ///
    str32 outcome ///
    str16 endovar ///
    str16 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

tempfile out_sizes
capture postclose handle_sizes
postfile handle_sizes ///
    str32 sample_tag ///
    str16 spec_tag ///
    double n_obs n_firms ///
    using `out_sizes', replace

// Outcomes for follow-ups (keep minimal; expand if needed)
local outcomes cb_log1p_raised_usd cb_log_raised_usd

// Helper: post sample sizes for the current data snapshot
program define __post_size
    syntax, SAMPLE(string) SPEC(string)
    quietly count
    local n_obs = r(N)
    preserve
        keep firm_id_num
        duplicates drop
        quietly count
        local n_firms = r(N)
    restore
    post handle_sizes ("`sample'") ("`spec'") (`n_obs') (`n_firms')
end

// Helper: run single-endog (var3) spec on current sample
program define __run_single_endog
    syntax, SAMPLE(string) SPEC(string) OUTCOME(name)

    local sample_tag "`sample'"
    local spec_tag "`spec'"
    local y "`outcome'"

    // Skip outcome if empty
    quietly count if !missing(`y')
    if r(N) == 0 exit

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
    reghdfe `y' var3 var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
    local N = e(N)
    foreach p in var3 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_reg ("`sample_tag'") ("`spec_tag'") ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (.) (`N')
    }

    // IV
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
        post handle_reg ("`sample_tag'") ("`spec_tag'") ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`pF') (`N')
    }

    // First stage for var3
    estimates restore _ivreg2_var3
    local N_fs = e(N)
    foreach z in var6 var4 {
        local b    = _b[`z']
        local se   = _se[`z']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("`sample_tag'") ("`spec_tag'") ("`y'") ("var3") ("`z'") ///
            (`b') (`se') (`pval') ///
            (`F3') (`rkf') (`N_fs')
    }
end

// Helper: run interaction spec (two endogenous vars: var3 and var3_out)
program define __run_geo_interaction
    syntax, SAMPLE(string) SPEC(string) OUTCOME(name)

    local sample_tag "`sample'"
    local spec_tag "`spec'"
    local y "`outcome'"

    quietly count if !missing(`y')
    if r(N) == 0 exit

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    capture drop outside_ny_sf var3_out var6_out
    gen byte outside_ny_sf = (hq_ny_sf == 0) if hq_ny_sf < .
    gen double var3_out = var3 * outside_ny_sf
    gen double var6_out = var6 * outside_ny_sf

    // OLS
    reghdfe `y' var3 var3_out var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num)
    local N = e(N)
    foreach p in var3 var3_out var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_reg ("`sample_tag'") ("`spec_tag'") ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (.) (`N')
    }

    // IV (two endogenous regressors)
    ivreghdfe `y' (var3 var3_out = var6 var6_out) var4, absorb(firm_id_num yh_num) vce(cluster firm_id_num) savefirst
    local rkf = e(rkf)
    local N = e(N)
    matrix FS = e(first)
    local F3 = FS[4,1]
    local F3o = FS[4,2]

    foreach p in var3 var3_out var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        local pF = .
        if "`p'" == "var3" local pF = `F3'
        if "`p'" == "var3_out" local pF = `F3o'
        post handle_reg ("`sample_tag'") ("`spec_tag'") ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`pF') (`N')
    }

    // First stages for var3 and var3_out
    estimates restore _ivreg2_var3
    local N_fs = e(N)
    foreach z in var6 var6_out var4 {
        local b    = _b[`z']
        local se   = _se[`z']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("`sample_tag'") ("`spec_tag'") ("`y'") ("var3") ("`z'") ///
            (`b') (`se') (`pval') ///
            (`F3') (`rkf') (`N_fs')
    }
    estimates restore _ivreg2_var3_out
    local N_fs = e(N)
    foreach z in var6 var6_out var4 {
        local b    = _b[`z']
        local se   = _se[`z']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("`sample_tag'") ("`spec_tag'") ("`y'") ("var3_out") ("`z'") ///
            (`b') (`se') (`pval') ///
            (`F3o') (`rkf') (`N_fs')
    }
end

// 8) Run variants ------------------------------------------------------

// A) Baseline matched-private (no age restriction)
use `matched_private', clear
__post_size, sample("matched_private") spec("baseline")
foreach y of local outcomes {
    __run_single_endog, sample("matched_private") spec("baseline") outcome(`y')
}

// B) Age restrictions
foreach cut in 10 20 {
    use `matched_private', clear
    keep if age < `cut'
    __post_size, sample("matched_private") spec("age_lt`cut'")
    foreach y of local outcomes {
        __run_single_endog, sample("matched_private") spec("age_lt`cut'") outcome(`y')
    }
}

// C) Intensive margin: drop zeros (positive dollars only)
use `matched_private', clear
keep if cb_raised_usd > 0
__post_size, sample("matched_private") spec("pos_usd_only")
foreach y of local outcomes {
    __run_single_endog, sample("matched_private") spec("pos_usd_only") outcome(`y')
}

// D) Restrict to firms that ever had a round (cb_round_count>0 at any point)
use `matched_private', clear
keep if ever_round == 1
__post_size, sample("matched_private") spec("firms_ever_round")
foreach y of local outcomes {
    __run_single_endog, sample("matched_private") spec("firms_ever_round") outcome(`y')
}

// E) Geography subsamples
use `matched_private', clear
keep if hq_ny_sf == 1
__post_size, sample("matched_private") spec("hq_ny_sf")
foreach y of local outcomes {
    __run_single_endog, sample("matched_private") spec("hq_ny_sf") outcome(`y')
}

use `matched_private', clear
keep if hq_ny_sf == 0
__post_size, sample("matched_private") spec("hq_outside_ny_sf")
foreach y of local outcomes {
    __run_single_endog, sample("matched_private") spec("hq_outside_ny_sf") outcome(`y')
}

// F) Geography interaction spec (full sample, requires non-missing hq_ny_sf)
use `matched_private', clear
keep if hq_ny_sf < .
__post_size, sample("matched_private") spec("geo_interaction")
foreach y of local outcomes {
    __run_geo_interaction, sample("matched_private") spec("geo_interaction") outcome(`y')
}

// 9) Export results ----------------------------------------------------
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

log close _all
