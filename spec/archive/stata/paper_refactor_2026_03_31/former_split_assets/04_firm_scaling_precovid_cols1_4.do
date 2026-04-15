*============================================================*
* Asset 04: firm_scaling_precovid_cols1_4.tex
* Self-contained baseline + growth-split firm-scaling exports.
*============================================================*

args sample_variant
if "`sample_variant'" == "" local sample_variant "precovid"
if "`sample_variant'" != "precovid" {
    di as error "Asset 04 only supports the precovid firm panel variant."
    exit 198
}

local asset_stem "04_firm_scaling_precovid_cols1_4"

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
log using "$LOG_DIR/`asset_stem'.log", replace text

local result_root "$results/`asset_stem'"
cap mkdir "`result_root'"
cap mkdir "`result_root'/initial"
cap mkdir "`result_root'/growth_split"

capture which reghdfe
if _rc {
    di as error "Required package 'reghdfe' not found."
    exit 199
}
capture which ivreghdfe
if _rc {
    di as error "Required package 'ivreghdfe' not found."
    exit 199
}

local firm_panel "$processed_data/firm_panel.dta"
capture confirm file "`firm_panel'"
if _rc {
    di as error "Missing firm panel: `firm_panel'"
    exit 601
}

di as text "Running asset 04 initial column export"
use "`firm_panel'", clear

capture postclose handle_initial
tempfile out_initial
postfile handle_initial ///
    str8   model_type ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out_initial', replace

local outcome_name growth_rate_we
summarize `outcome_name' if covid == 0, meanonly
local pre_mean = r(mean)

reghdfe `outcome_name' var3 var4, absorb(firm_id yh) vce(cluster firm_id)
local N = e(N)
foreach p in var3 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_initial ("OLS") ("`outcome_name'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') ///
        (.) (`N')
}

ivreghdfe `outcome_name' (var3 = var6) var4, ///
    absorb(firm_id yh) vce(cluster firm_id) savefirst
local rkf = e(rkf)
local N = e(N)
foreach p in var3 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_initial ("IV") ("`outcome_name'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') ///
        (`rkf') (`N')
}

postclose handle_initial
use `out_initial', clear
export delimited using "`result_root'/initial/consolidated_results.csv", replace delimiter(",") quote

di as text "Running asset 04 growth-split column export"
use "`firm_panel'", clear

capture postclose handle_growth
tempfile out_growth
postfile handle_growth ///
    str8   model_type ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out_growth', replace

local outcome_vars growth_rate_we join_rate_we leave_rate_we
foreach outcome_name of local outcome_vars {
    summarize `outcome_name' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `outcome_name' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_growth ("OLS") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe ///
        `outcome_name' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_growth ("IV") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }
}

postclose handle_growth
use `out_growth', clear
export delimited using "`result_root'/growth_split/consolidated_results.csv", replace delimiter(",") quote

log close
