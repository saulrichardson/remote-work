// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



*====================================================================*
*  user_w_geo_triple_diff.do
*  — Triple-difference specification using geography-only wages
*====================================================================*

clear all
set more off

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

*--------------------------------------------------------------------*
* 0) Dependencies and globals
*--------------------------------------------------------------------*
capture which reghdfe
if _rc {
    di as error "reghdfe package is required but not installed."
    exit 459
}

capture which ivreghdfe
if _rc {
    di as error "ivreghdfe package is required but not installed."
    exit 459
}

local data_path "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
local results_path "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

global processed_data "`data_path'"
global results "`results_path'"

*--------------------------------------------------------------------*
* 1) Ensure geography component is up to date
*--------------------------------------------------------------------*
do "/Users/saul/Dropbox/Remote Work Startups/main/spec/scratch/w_geo_two_step.do" "`panel_variant'"

*--------------------------------------------------------------------*
* 2) Load enriched panel
*--------------------------------------------------------------------*
use "`data_path'/user_panel_w_geo_twostep_`panel_variant'.dta", clear

foreach reqvar in w_geo_hat var3 var4 var5 var6 var7 user_id firm_id yh covid {
    capture confirm variable `reqvar'
    if _rc {
        di as error "Required variable `reqvar' is missing after geography merge."
        exit 465
    }
}

capture confirm variable lwage
if _rc {
    di as error "Variable lwage is required to build residual wages."
    exit 466
}

assert !missing(w_geo_hat, var3, var4, var5, var6, var7, user_id, firm_id, yh, covid)

*--------------------------------------------------------------------*
* 3) Prepare log and result directory
*--------------------------------------------------------------------*
local specname "user_w_geo_twostep_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar ///
    str40  param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

*--------------------------------------------------------------------*
* 4) Run OLS and IV triple-diff on geography-only and residual wages
*--------------------------------------------------------------------*
local outcome "w_geo_hat"
local fs_done 0

foreach outcome in `outcome' {
    quietly summarize `outcome' if covid == 0, meanonly
    assert r(N) > 0
    local pre_mean = r(mean)

    reghdfe `outcome' var3 var5 var4, absorb(user_id#firm_id yh) vce(cluster user_id)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe ///
        `outcome' (var3 var5 = var6 var7) var4, ///
        absorb(user_id#firm_id yh) vce(cluster user_id) savefirst

    local rkf = e(rkf)
    local N   = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`outcome'") ("`p'") ///
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

*--------------------------------------------------------------------*
* 5) Export results
*--------------------------------------------------------------------*
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"

capture log close
