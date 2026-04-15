*============================================================*
* firm_scaling_crunchbase_fundraising_core4_fe_robustness.do
*
* Appendix robustness: run the same 4-column FE/age<20 table for each
* of the four "core" Crunchbase fundraising outcomes used in the main table:
*   (A) Any USD raised (cb_any_raised)
*   (B) Series A+ round (cb_seriesAplus_round)
*   (C) USD raised in levels (cb_raised_usd)
*   (D) USD raised rank (q100) (cb_raised_usd_q100)
*
* Sample (baseline for all columns)
*   - Crunchbase-matched private firms: cb_matched==1 and public!=1
*
* Columns (fe_tag)
*   (1) ind_yh   : firm FE + industry×half-year shocks
*   (2) state_yh : firm FE + HQ-state×half-year shocks
*   (3) both_yh  : firm FE + industry×yh + HQ-state×yh
*   (4) age_lt20 : firm FE + half-year FE, restricted to age < 20
*
* Spec (pure)
*   y_it = β var3_it + FE + e_it
*   IV: (var3 = var6), clustered by firm
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_core4_fe_robustness/
*     consolidated_results.csv
*============================================================*

// --------------------------------------------------------------------------
// 0) Bootstrap paths + logging
// --------------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

local specname "14_firm_scaling_crunchbase_fundraising_core4_fe_robustness_cb_raised_usd"
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

// --------------------------------------------------------------------------
// 1) Load Crunchbase-augmented firm panel (CSV)
// --------------------------------------------------------------------------
local in_csv "$processed_data/firm_panel_with_cb_funding.csv"
capture confirm file "`in_csv'"
if _rc {
    di as error "Missing input panel: `in_csv'"
    di as error "Build it first via:"
    di as error "  python src/py/build_firm_panel_with_crunchbase_funding.py"
    exit 601
}

import delimited using "`in_csv'", clear varnames(1) case(preserve) stringcols(_all)

// --------------------------------------------------------------------------
// 2) Required variables + hygiene
// --------------------------------------------------------------------------
local required_vars ///
    firm_id yh_num covid ///
    industry_id hqstate age ///
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

local maybe_numeric ///
    firm_id yh_num covid ///
    age ///
    cb_matched public ///
    cb_raised_usd cb_seriesAplus_round ///
    var3 var6

foreach v of local maybe_numeric {
    capture confirm numeric variable `v'
    if _rc {
        destring `v', replace ignore(" ,")
    }
}

capture confirm numeric variable yh_num
if _rc {
    destring yh_num, replace ignore(" ,")
}
format yh_num %th

// firm_id must be numeric for clustering; encode if needed.
capture confirm numeric variable firm_id
if _rc {
    encode firm_id, gen(firm_id_num)
}
else {
    gen long firm_id_num = firm_id
}

// HQ state FE requires a numeric ID (encode from string).
capture drop hqstate_id
capture confirm string variable hqstate
if _rc {
    di as error "hqstate must be a string variable in `in_csv' to encode hqstate_id."
    exit 198
}
encode hqstate, gen(hqstate_id)

// Industry FE requires a numeric ID; encode string industries if needed.
capture drop industry_id_num
capture confirm numeric variable industry_id
if _rc {
    capture confirm string variable industry_id
    if _rc {
        di as error "industry_id must be numeric or string in `in_csv'."
        exit 198
    }
    encode industry_id, gen(industry_id_num)
}
else {
    gen long industry_id_num = industry_id
}

// --------------------------------------------------------------------------
// 3) Baseline sample policy: matched + private (age restriction is col 4)
// --------------------------------------------------------------------------
keep if cb_matched == 1
keep if public != 1

count if missing(age)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing age (needed for age < 20 column)."
    exit 459
}

// Guardrail: matched rows should use explicit zeros (not missing).
count if missing(cb_raised_usd)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing cb_raised_usd (should be 0)."
    exit 459
}
count if missing(cb_seriesAplus_round)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing cb_seriesAplus_round (should be 0)."
    exit 459
}

// --------------------------------------------------------------------------
// 4) Outcomes (construct if needed)
// --------------------------------------------------------------------------
capture drop cb_any_raised cb_raised_usd_q100

gen byte cb_any_raised = (cb_raised_usd > 0) if !missing(cb_raised_usd)
label var cb_any_raised "1{Any USD raised in half-year}"

// Percentile-rank outcome computed within the baseline matched-private sample (by half-year).
capture noisily bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
if _rc {
    di as error "Unable to compute cb_raised_usd_q100 via: bys yh_num: egen ... = xtile(...), nquantiles(100)"
    di as error "This requires egenmore. Install once via:  ssc install egenmore, replace"
    exit 199
}
label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

local outcomes cb_any_raised cb_seriesAplus_round cb_raised_usd cb_raised_usd_q100

// --------------------------------------------------------------------------
// 5) Save baseline panel (avoid stateful filters across columns/outcomes)
// --------------------------------------------------------------------------
tempfile panel_tmp
save `panel_tmp', replace
global PANEL_TMP "`panel_tmp'"

// --------------------------------------------------------------------------
// 6) Results setup (postfile)
// --------------------------------------------------------------------------
local out_dir "$results/`specname'"
capture mkdir "`out_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str12   model_type ///
    str12   fe_tag ///
    str32   outcome ///
    str12   param ///
    double  coef se pval pre_mean ///
    double  rkf nobs ///
    using `out', replace

program define run_fe
    args tag feopt age_lt20 yvar

    use "$PANEL_TMP", clear

    if "`age_lt20'" == "1" {
        keep if age < 20
    }

    local y "`yvar'"

    // Outcome sanity: require at least some variation.
    quietly count if !missing(`y')
    if r(N) == 0 {
        post handle ("OLS") ("`tag'") ("`y'") ("var3") (.) (.) (.) (.) (.) (0)
        post handle ("IV")  ("`tag'") ("`y'") ("var3") (.) (.) (.) (.) (.) (0)
    }
    else {
        quietly summarize `y'
        if r(sd) == 0 {
            quietly summarize `y' if covid == 0, meanonly
            local pre_mean = r(mean)
            post handle ("OLS") ("`tag'") ("`y'") ("var3") (.) (.) (.) (`pre_mean') (.) (r(N))
            post handle ("IV")  ("`tag'") ("`y'") ("var3") (.) (.) (.) (`pre_mean') (.) (r(N))
        }
        else {
            // ---------------- OLS ----------------
            reghdfe `y' var3, `feopt' vce(cluster firm_id_num)
            local N = e(N)
            quietly summarize `y' if e(sample) & covid == 0, meanonly
            local pre_mean_ols = r(mean)

            local b  = _b[var3]
            local se = _se[var3]
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("OLS") ("`tag'") ("`y'") ("var3") ///
                (`b') (`se') (`pval') (`pre_mean_ols') ///
                (.) (`N')

            // ---------------- IV ----------------
            ivreghdfe `y' (var3 = var6), `feopt' vce(cluster firm_id_num)
            local rkf = e(rkf)
            local N = e(N)
            quietly summarize `y' if e(sample) & covid == 0, meanonly
            local pre_mean_iv = r(mean)

            local b  = _b[var3]
            local se = _se[var3]
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("IV") ("`tag'") ("`y'") ("var3") ///
                (`b') (`se') (`pval') (`pre_mean_iv') ///
                (`rkf') (`N')
        }
    }
end

// --------------------------------------------------------------------------
// 7) Run table columns for each outcome
// --------------------------------------------------------------------------
foreach y of local outcomes {
    run_fe "ind_yh"   "absorb(firm_id_num industry_id_num#yh_num)" 0 "`y'"
    run_fe "state_yh" "absorb(firm_id_num hqstate_id#yh_num)" 0 "`y'"
    run_fe "both_yh"  "absorb(firm_id_num industry_id_num#yh_num hqstate_id#yh_num)" 0 "`y'"
    run_fe "age_lt20" "absorb(firm_id_num yh_num)" 1 "`y'"
}

// --------------------------------------------------------------------------
// 8) Export
// --------------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`out_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ Wrote: `out_dir'/consolidated_results.csv"
log close _all
