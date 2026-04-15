*============================================================*
* firm_scaling_crunchbase_fundraising_core4_event_study_ols.do
*
* Purpose
*   Export OLS "event-study" dynamics for the Crunchbase fundraising outcomes
*   used in the main core-4 table (Table: Crunchbase Fundraising Outcomes).
*
* Spec (OLS, dynamic)
*   y_it = Σ_{t≠2019H2} β_t [ Remote_i × 1{half-year = t} ] + FE_firm + FE_time + e_it
*   Clustered SEs by firm.
*
* Interpretation
*   β_t is the remote-slope in half-year t relative to the omitted baseline
*   half-year (2019H2).
*
* Sample
*   - Crunchbase-matched firms (cb_matched == 1)
*   - Drop public firms (public != 1)
*
* Outcomes
*   - cb_any_raised:         1{USD raised > 0} in half-year
*   - cb_seriesAplus_round:  1{Series A-or-higher round} in half-year
*   - cb_raised_usd_mil:     USD raised in half-year (millions; includes zeros)
*   - cb_raised_usd_q100:    within-half-year percentile bin (1..100) of USD raised
*
* Inputs
*   data/clean/firm_panel_with_cb_funding.csv
*
* Outputs
*   results/raw/firm_scaling_crunchbase_fundraising_core4_event_study/
*     ols_cb_any_raised.csv
*     ols_cb_seriesAplus_round.csv
*     ols_cb_raised_usd_mil.csv
*     ols_cb_raised_usd_q100.csv
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

local specname "firm_scaling_crunchbase_fundraising_core4_event_study_ols"
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

// --------------------------------------------------------------------------
// 1) Load Crunchbase-augmented firm panel (CSV)
// --------------------------------------------------------------------------
local in_csv "$processed_data/firm_panel_with_cb_funding.csv"
capture confirm file "`in_csv'"
if _rc {
    di as error "Missing input panel: `in_csv'"
    di as error "Build it first via:"
    di as error "  python src/py/build_firm_scaling_crunchbase_outcomes.py"
    exit 601
}

import delimited using "`in_csv'", clear varnames(1) case(preserve) stringcols(_all)

// --------------------------------------------------------------------------
// 2) Required variables + hygiene
// --------------------------------------------------------------------------
local required_vars ///
    firm_id yh_num ///
    cb_matched public ///
    remote ///
    cb_raised_usd cb_seriesAplus_round

foreach v of local required_vars {
    capture confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in `in_csv'."
        exit 198
    }
}

local maybe_numeric ///
    firm_id yh_num ///
    cb_matched public ///
    remote ///
    cb_raised_usd cb_seriesAplus_round

foreach v of local maybe_numeric {
    capture confirm variable `v'
    if !_rc {
        capture confirm numeric variable `v'
        if _rc {
            destring `v', replace ignore(" ,")
        }
    }
}

// Ensure yh_num is numeric %th for fixed effects and labeling.
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

// Sample: matched private
keep if cb_matched == 1
keep if public != 1

// Guardrail: matched rows should use explicit zeros (not missing)
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
count if missing(remote)
if r(N) > 0 {
    di as error "Found " r(N) " matched-private row(s) with missing remote."
    exit 459
}

// --------------------------------------------------------------------------
// 3) Construct outcomes (core 4, event-study friendly units)
// --------------------------------------------------------------------------
capture drop cb_any_raised cb_raised_usd_q100 cb_raised_usd_mil

gen byte cb_any_raised = (cb_raised_usd > 0) if !missing(cb_raised_usd)
label var cb_any_raised "1{Any USD raised in half-year}"

gen double cb_raised_usd_mil = cb_raised_usd/1000000
label var cb_raised_usd_mil "USD raised in half-year (millions; includes zeros)"

// Percentile rank (q100) computed within the matched-private sample by half-year.
capture noisily bys yh_num: egen cb_raised_usd_q100 = xtile(cb_raised_usd), nquantiles(100)
if _rc {
    di as error "Unable to compute cb_raised_usd_q100 via: bys yh_num: egen ... = xtile(...), nquantiles(100)"
    di as error "This requires egenmore. Install once via:  ssc install egenmore, replace"
    exit 199
}
label var cb_raised_usd_q100 "Within-half-year percentile bin (1-100) of USD raised"

// --------------------------------------------------------------------------
// 4) Event-study time mapping (baseline = 2019H2)
// --------------------------------------------------------------------------
tab yh_num, gen(time)

tempvar tmpindex
preserve
    contract yh_num
    sort yh_num
    gen `tmpindex' = _n

    local target19h2 = yh(2019, 2)
    quietly summarize `tmpindex' if yh_num == `target19h2'
    local idx19h2 = r(mean)
    if missing(`idx19h2') {
        di as error "Baseline half-year 2019H2 not found in sample."
        exit 498
    }
    di as text "Baseline index for 2019H2 is `idx19h2'"

    gen str7 period_label = subinstr(string(yh_num, "%th"), "h", "H", .)
    keep yh_num `tmpindex' period_label
    rename `tmpindex' period
    rename yh_num yh
    tempfile yhmap
    save `yhmap'
restore

preserve
    contract yh_num
    local total_periods = _N
restore

// --------------------------------------------------------------------------
// 5) Generate Remote×time interactions
// --------------------------------------------------------------------------
forval t = 1/`total_periods' {
    gen double rem_`t' = remote * time`t'
}

local rem_vars ""
forval t = 1/`total_periods' {
    if `t' == `idx19h2' continue
    local rem_vars `rem_vars' rem_`t'
}

// --------------------------------------------------------------------------
// 6) Run OLS event study for each outcome + export CSVs for plotting
// --------------------------------------------------------------------------
local out_dir "$results/firm_scaling_crunchbase_fundraising_core4_event_study"
capture mkdir "`out_dir'"

local outcomes cb_any_raised cb_seriesAplus_round cb_raised_usd_mil cb_raised_usd_q100

foreach y of local outcomes {

    reghdfe `y' `rem_vars', absorb(firm_id_num yh_num) vce(cluster firm_id_num)

    matrix define escoef = J(`total_periods',3,.)
    forval i = 1/`total_periods' {
        if `i' == `idx19h2' {
            continue
        }
        local b  = _b[rem_`i']
        local se = _se[rem_`i']
        matrix escoef[`i',1] = `b'
        matrix escoef[`i',2] = `b' - 1.96*`se'
        matrix escoef[`i',3] = `b' + 1.96*`se'
    }
    matrix colnames escoef = b lb ub

    preserve
        clear
        svmat double escoef, names(col)
        gen period     = _n
        gen event_time = period - `idx19h2'
        gen omitted    = period == `idx19h2'
        replace b  = . if omitted
        replace lb = . if omitted
        replace ub = . if omitted
        merge 1:1 period using `yhmap', nogen
        gen str8  estimator = "OLS"
        gen str80 outcome   = "`y'"
        order outcome estimator period period_label event_time omitted b lb ub yh
        export delimited using "`out_dir'/ols_`y'.csv", replace
    restore
}

log close

