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
*  spec/growth_mechanisms_demo.do
*  ------------------------------------------------------------------
*  Demonstration of growth mechanisms horse race with key specifications
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

local specname "growth_mechanisms_demo_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

*--------------------------------------------------------------------*
* 1. Load main panel and create simple growth indicators
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Get firm controls
preserve
    use "$processed_data/firm_panel.dta", clear
    gen companyname_c = lower(companyname)
    capture gen byte covid = (yh >= 120)
    collapse (mean) rent (mean) hhi_1000 if covid, by(companyname_c)
    xtile high_rent = rent, nq(2)
    xtile high_hhi = hhi_1000, nq(2)
    replace high_rent = (high_rent == 2)
    replace high_hhi = (high_hhi == 2)
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

* Simple growth indicator (use existing growth_rate_we if available)
gen high_growth = 0
capture replace high_growth = (growth_rate_we > 0) if !missing(growth_rate_we)

*--------------------------------------------------------------------*
* 2. Create interaction variables
*--------------------------------------------------------------------*
gen var17 = covid * high_growth
gen var18 = covid * high_growth * startup
gen var21 = covid * high_rent
gen var22 = covid * high_rent * startup
gen var23 = covid * high_hhi
gen var24 = covid * high_hhi * startup

*--------------------------------------------------------------------*
* 3. Setup postfile
*--------------------------------------------------------------------*
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  /// 
    str40  spec        ///
    str10  param       ///
    double coef se pval pre_mean rkf nobs /// 
    using `out', replace

*--------------------------------------------------------------------*
* 4. Pre-COVID mean
*--------------------------------------------------------------------*
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

*--------------------------------------------------------------------*
* 5. Run key specifications
*--------------------------------------------------------------------*

* Specification 1: Baseline
di "Running baseline specification..."

reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("baseline") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("baseline") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 2: Growth
di "Running growth specification..."

reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 3: Rent
di "Running rent specification..."

reghdfe total_contributions_q100 var3 var5 var4 var21 var22, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("rent") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var21 var22, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("rent") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 4: HHI
di "Running HHI specification..."

reghdfe total_contributions_q100 var3 var5 var4 var23 var24, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("hhi") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var23 var24, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("hhi") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 5: All combined
di "Running combined specification..."

reghdfe total_contributions_q100 var3 var5 var4 var17 var18 var21 var22 var23 var24, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("growth_rent_hhi") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18 var21 var22 var23 var24, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("growth_rent_hhi") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

*--------------------------------------------------------------------*
* 6. Save results
*--------------------------------------------------------------------*
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

di as result "Results saved to `result_dir'/consolidated_results.csv"

log close
