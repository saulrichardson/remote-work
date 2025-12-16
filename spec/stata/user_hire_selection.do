*============================================================*
* user_hire_selection.do                                    *
* Two-column selection test around hires:                   *
*   (1) prior productivity (mean over last 4 half-years)    *
*   (2) change in productivity after hire (new-old)         *
* RHS: var3 var4 var5 + hiring half-year FE; cluster firm.  *
*============================================================*

// Parse optional panel variant (default: precovid)
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_hire_selection_`panel_variant'

// Bootstrap paths
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

// 1) Load hire-level panel
use "$clean_data/user_hire_selection_panel_`panel_variant'.dta", clear

// 2) Output setup
local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str8   model_type ///
    str40  outcome    ///
    str40  param      ///
    double coef se pval pre_mean ///
    double rkf nobs    ///
    using `out', replace

// 3) Outcomes to estimate
local outcomes old_prod delta_prod

foreach y of local outcomes {
    di as text "→ OLS outcome: `y'"

    summarize `y', meanonly
    local pre_mean = r(mean)

    reghdfe `y' var3 var4 var5 i.hire_half_index, vce(cluster firm_id)
    local N = e(N)

    foreach p in var3 var4 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

        post handle ("OLS") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`N')
    }
}

// 4) Export
postclose handle
use `out', clear
export delimited using "`result_dir'/selection_results.csv", replace delimiter(",") quote

di as result "→ Selection results: `result_dir'/selection_results.csv"
log close
