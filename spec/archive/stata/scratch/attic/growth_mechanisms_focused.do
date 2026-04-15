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
*  spec/growth_mechanisms_focused.do
*  ------------------------------------------------------------------
*  Focused analysis: Baseline, Endogenous Growth, Exogenous Growth
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

local specname "growth_mechanisms_focused_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

*--------------------------------------------------------------------*
* 1. Load main panel
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

*--------------------------------------------------------------------*
* 2. Get firm controls for residualization
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    gen companyname_c = lower(companyname)
    capture gen byte covid = (yh >= 120)
    collapse (mean) rent (mean) hhi_1000 if covid, by(companyname_c)
    tempfile firm_controls
    save `firm_controls'
restore

*--------------------------------------------------------------------*
* 3. Calculate growth measures
*--------------------------------------------------------------------*
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    
    gen yh = hofd(date)
    format yh %th
    
    * Drop June 2022 outliers
    drop if date == 22797
    
    collapse (last) total_employees date, by(companyname yh)
    
    gen byte covid = (yh >= 120)
    
    * Calculate static growth measure
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    gen growth_raw = (total_employees1 - total_employees0) / total_employees0
    winsor2 growth_raw, cuts(1 99)
    
    * Merge firm controls for residualization
    gen companyname_c = lower(companyname)
    merge 1:1 companyname_c using `firm_controls', keep(match master) nogen
    
    * For now, set industry and MSA growth to 0 (simplification)
    gen ind_growth_lo = 0
    gen msa_growth_lo = 0
    
    * Residualize growth on controls
    reg growth_raw rent hhi_1000 ind_growth_lo msa_growth_lo
    predict growth_resid, residuals
    
    * Create binary indicators
    quietly sum growth_raw, detail
    gen high_growth_raw = (growth_raw > r(p50)) if !missing(growth_raw)
    
    quietly sum growth_resid, detail
    gen high_growth_resid = (growth_resid > r(p50)) if !missing(growth_resid)
    
    keep companyname growth_raw growth_resid high_growth_raw high_growth_resid
    tempfile growth_measures
    save `growth_measures'
restore

*--------------------------------------------------------------------*
* 4. Merge everything back to main panel
*--------------------------------------------------------------------*
merge m:1 companyname using `growth_measures', keep(match) nogen

*--------------------------------------------------------------------*
* 5. Create interaction variables
*--------------------------------------------------------------------*
* Endogenous growth interactions
gen var17 = covid * high_growth_raw
gen var18 = covid * high_growth_raw * startup

* Exogenous growth interactions
gen var19 = covid * high_growth_resid
gen var20 = covid * high_growth_resid * startup

*--------------------------------------------------------------------*
* 6. Setup postfile
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
* 7. Pre-COVID mean
*--------------------------------------------------------------------*
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

*--------------------------------------------------------------------*
* 8. Run three specifications
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

* Specification 2: Endogenous Growth
di "Running endogenous growth specification..."

reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("endo_growth") ("`p'") ///
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
    post handle ("IV") ("endo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 3: Exogenous Growth
di "Running exogenous growth specification..."

reghdfe total_contributions_q100 var3 var5 var4 var19 var20, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("exo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var19 var20, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("exo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

*--------------------------------------------------------------------*
* 9. Save results
*--------------------------------------------------------------------*
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

di as result "Results saved to `result_dir'/consolidated_results.csv"

* Show residualization R-squared
di _n "=== Growth Residualization Statistics ==="
di "See regression output above for R-squared from growth residualization"

log close
