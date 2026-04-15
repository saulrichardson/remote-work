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



*============================================================*
*  user_wage.do
*  — Export OLS, IV, and first-stage results for worker wages
*    The optional argument selects the user panel variant:
*      unbalanced | balanced | precovid   (default = precovid)
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_wage_`panel_variant'
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


// 0) Setup environment -------------------------------------------------------
do "../globals.do"

// 1) Load worker-level panel -------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

capture drop _merge

// Ensure salary is numeric and usable ---------------------------------------
capture confirm numeric variable salary
if _rc {
    quietly destring salary, replace
}

drop if missing(salary) | salary <= 0

capture confirm variable log_salary
if _rc {
    gen log_salary = ln(salary)
}
label var log_salary "Log salary (annual)"

// 2) Prepare output dir & reset postfiles -----------------------------------
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

// First-stage results
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar ///
    str40  param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

// 3) Loop over wage outcomes -------------------------------------------------
local outcomes log_salary
local fs_done 0

foreach y of local outcomes {
    di as text "→ Processing outcome: `y'"

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----- OLS -------------------------------------------------------------
    reghdfe `y' var3 var5 var4, absorb(user_id#firm_id yh) ///
        vce(cluster user_id)
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

    // ----- IV (2nd stage) --------------------------------------------------
    ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(user_id#firm_id yh) vce(cluster user_id) savefirst

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

// 4) Close & export ---------------------------------------------------------
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
