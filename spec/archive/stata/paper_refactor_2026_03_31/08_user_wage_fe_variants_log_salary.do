*=====================================================================*
* user_wage_fe_variants.do
* Estimates how remote-work adoption influences Revelio's imputed log wages under
* five alternative fixed-effect structures.  The script accepts any user-panel
* variant (default: precovid), applies the same teleworkability instrument used
* in the productivity analysis, and exports both second-stage results and
* first-stage diagnostics for the wage table.  The exported FE variants align
* with the mini-writeup columns:
*
*     user_firm_yh                – firm + user + time FE (baseline)
*     userfirm_yh                 – firm × user + time FE ("match")
*     userfirm_yh_title           – match FE + occupation title FE
*     userfirm_yh_title_location  – match FE + occupation title + job location FE
*=====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_wage_fe_variants_`panel_variant'

version 17.0

// ------------------------------------------------------------------
// Environment setup (requires running from project root unless
// PROJECT_ROOT/STATAROOT is already defined)
// ------------------------------------------------------------------
local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    local __env_root: env PROJECT_ROOT
    if "`__env_root'" == "" local __env_root: env STATAROOT
    if "`__env_root'" != "" local __bootstrap "`__env_root'/spec/stata/_bootstrap.do"
}
if !fileexists("`__bootstrap'") {
    di as error "Run this spec from the repository root (project_root/spec/stata/_bootstrap.do not found)."
    exit 601
}
do "`__bootstrap'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text



// ------------------------------------------------------------------
// Data prep
// ------------------------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear


capture confirm numeric variable salary
if _rc quietly destring salary, replace
drop if missing(salary) | salary <= 0

capture confirm variable log_salary
if _rc gen log_salary = ln(salary)
label var log_salary "Log salary (annual)"

capture confirm numeric variable firm_id
if _rc encode companyname, gen(firm_id)
label var firm_id "Firm identifier"

capture drop occ_title_id
egen long occ_title_id = group(title), missing
label var occ_title_id "Occupation title FE id"

capture drop location_id
egen long location_id = group(location), missing
label var location_id "Job location FE id"

tempfile panel_ready
save `panel_ready', replace

// ------------------------------------------------------------------
// Output containers
// ------------------------------------------------------------------
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  fe_tag ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str40  fe_tag ///
    str8   endovar ///
    str40  param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_fs', replace

di as text ">> Running user_wage_fe_variants.do"
di as text "   - CWD: `c(pwd)'"
di as text "   - Source: `c(filename)'"

// ------------------------------------------------------------------
// FE specifications
// ------------------------------------------------------------------
local outcome log_salary

local fe_variants "user_firm_yh userfirm_yh userfirm_yh_title userfirm_yh_title_location"

foreach tag of local fe_variants {

    if "`tag'" == "user_firm_yh" {
        local feopt "absorb(user_id firm_id yh)"
    }
    else if "`tag'" == "userfirm_yh" {
        local feopt "absorb(user_id#firm_id yh)"
    }
    else if "`tag'" == "userfirm_yh_title" {
        local feopt "absorb(user_id#firm_id yh occ_title_id)"
    }
    else if "`tag'" == "userfirm_yh_title_location" {
        local feopt "absorb(user_id#firm_id yh occ_title_id location_id)"
    }
    else {
        continue
    }

    use `panel_ready', clear
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
