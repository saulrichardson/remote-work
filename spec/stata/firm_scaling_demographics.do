*============================================================*
* firm_scaling_demographics.do
* Runs the firm-level scaling spec on demographic composition
* outcomes (female shares/rates, age means). Built to mirror
* firm_scaling.do without touching the original outputs.
*============================================================*

// 0) Setup environment
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"


// 1) Load merged firm panel with demographics
use "$processed_data/firm_panel_demographics.dta", clear


// 2) Prepare output dir & tempfile
local specname   "firm_scaling_demographics"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
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

// 3) Outcomes to estimate (shares/rates/ages)
local outcome_vars female_hires_share female_headcount_share ///
                   female_join_rate female_leave_rate ///
                   avg_age_hires avg_age_headcount

local fs_done = 0

foreach y of local outcome_vars {
    di as text "→ Processing `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // --- OLS ---
     reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)

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

    // --- IV (2nd stage) ---
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst

    local rkf   = e(rkf)
    local N_iv = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N_iv')
    }

    // First stage only once
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

// 4) Export
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

