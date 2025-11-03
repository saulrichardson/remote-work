*=====================================================================*
* user_wage_fe_variants.do
* Estimates how remote-work adoption influences Revelio's imputed log wages under four
* alternative fixed-effect structures (user–firm vs. user×firm, with and without
* occupation titles).  The script accepts any user-panel variant (default:
* precovid), applies the same teleworkability instrument used in the
* productivity analysis, and exports both second-stage results and first-stage
* diagnostics for the wage table.
*=====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_wage_fe_variants_`panel_variant'

capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

// ------------------------------------------------------------------
// Environment setup (supports external invocation via STATAROOT)
// ------------------------------------------------------------------
do "_bootstrap.do"

// ------------------------------------------------------------------
// Data prep
// ------------------------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

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

capture confirm numeric variable firm_id
if _rc {
    encode companyname, gen(firm_id)
    label var firm_id "Firm identifier"
}

capture drop occ_title_id
egen long occ_title_id = group(title), missing
label var occ_title_id "Occupation title FE id"

// ------------------------------------------------------------------
// Output containers
// ------------------------------------------------------------------
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str20  fe_tag ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str20  fe_tag ///
    str8   endovar ///
    str40  param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

// ------------------------------------------------------------------
// FE specifications
// ------------------------------------------------------------------
local outcome log_salary

foreach tag in user_firm_yh user_firm_yh_title userfirm_yh userfirm_yh_title {

    if "`tag'" == "user_firm_yh" {
        local feopt "absorb(user_id firm_id yh)"
    }
    else if "`tag'" == "user_firm_yh_title" {
        local feopt "absorb(user_id firm_id yh occ_title_id)"
    }
    else if "`tag'" == "userfirm_yh" {
        local feopt "absorb(user_id#firm_id yh)"
    }
    else if "`tag'" == "userfirm_yh_title" {
        local feopt "absorb(user_id#firm_id yh occ_title_id)"
    }
    else {
        continue
    }

    use "$processed_data/user_panel_`panel_variant'.dta", clear
    capture confirm numeric variable salary
    if _rc {
        quietly destring salary, replace
    }
    drop if missing(salary) | salary <= 0
    capture confirm variable log_salary
    if _rc {
        gen log_salary = ln(salary)
    }
    capture confirm numeric variable firm_id
    if _rc {
        encode companyname, gen(firm_id)
        label var firm_id "Firm identifier"
    }
    capture drop occ_title_id
    egen long occ_title_id = group(title), missing

    quietly summarize `outcome' if covid == 0, meanonly
    local pre_mean = r(mean)

    di as text "→ Spec: `tag' [`feopt']"

    // OLS ----------------------------------------------------------
    reghdfe `outcome' var3 var5 var4, `feopt' vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

        post handle ("OLS") ("`tag'") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    // IV -----------------------------------------------------------
    ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst

    local rkf = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

        post handle ("IV") ("`tag'") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    // First-stage diagnostics -------------------------------------
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

        post handle_fs ("`tag'") ("var3") ("`p'") ///
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

        post handle_fs ("`tag'") ("var5") ("`p'") ///
            (`b') (`se') (`pval') ///
            (`F5') (`rkf') (`N_fs')
    }
}

// ------------------------------------------------------------------
// Export
// ------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

di as result "→ Output directory: `result_dir'"
capture log close
