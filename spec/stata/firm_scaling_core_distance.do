*======================================================================*
* firm_scaling_core_distance.do
* Runs the canonical firm-scaling OLS/IV specification on new geography
* outcomes derived from core vs non-core CBSA headcounts.
*======================================================================*

version 17
clear all
set more off

*---- Bootstrap paths -------------------------------------------------*
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



*---- Load firm panel & merge new outcomes ----------------------------*
use "$processed_data/firm_panel.dta", clear
replace companyname = lower(companyname)

tempfile metrics
preserve
    import delimited "$processed_data/firm_core_distance_outcomes.csv", varnames(1) clear
    replace companyname = lower(strtrim(companyname))
    compress
    capture confirm numeric variable yh
    if _rc quietly destring yh, replace
    save `metrics'
restore

merge 1:1 companyname yh using `metrics', keep(master match) nogen

foreach v in core_share noncore_share share_far_050 share_far_250 noncore_core_ratio {
    capture confirm numeric variable `v'
    if _rc {
        di as error "Missing expected variable: `v'"
        exit 459
    }
}

*---- Results setup ---------------------------------------------------*
local specname "firm_scaling_core_distance"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

tempfile out
capture postclose handle
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
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

local outcome_vars ///
    core_headcount ///
    noncore_headcount ///
    headcount_far_050 ///
    headcount_far_250 ///
    core_share ///
    noncore_share ///
    share_far_050 ///
    share_far_250 ///
    avg_distance_km ///
    p90_distance_km ///
    noncore_core_ratio ///
    core_minus_noncore ///
    num_noncore_cbsa ///
    any_far_050 ///
    any_far_250

local fs_done = 0

foreach y of local outcome_vars {
    quietly summarize `y' if covid == 0
    local pre_mean = r(mean)

    *--- OLS ----------------------------------------------------------*
    capture noisily reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    if _rc {
        di as error "Skipping `y' – OLS regression failed (code `_rc')."
        continue
    }
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    *--- IV -----------------------------------------------------------*
    capture noisily ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    if _rc {
        di as error "Skipping `y' – IV regression failed (code `_rc')."
        continue
    }
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    if !`fs_done' {
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

        local fs_done 1
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

di as result "✓ Core-distance spec completed → `result_dir'"
log close
