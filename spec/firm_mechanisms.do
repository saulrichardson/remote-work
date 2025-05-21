*============================================================*
* do/firm_mechanisms_regressions.do
*  — Automated export of OLS, IV & first-stage F's
*    across 8 specification columns
*============================================================*

capture log close
local specname   "firm_mechanisms"
log using "log/`specname'.log", replace text


// 0) Globals + setup
do "../src/globals.do"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load & prepare once
use "$processed_data/firm_panel.dta", clear
gen seniority_4 = !inrange(seniority_levels,1,3)

// interactions
gen var8  = covid*rent
gen var9  = covid*rent*remote
gen var10 = teleworkable*covid*rent
gen var11 = covid*hhi_1000
gen var12 = covid*hhi_1000*remote
gen var13 = teleworkable*covid*hhi_1000
gen var14 = covid*seniority_4
gen var15 = covid*seniority_4*remote
gen var16 = teleworkable*covid*seniority_4

// 2) postfile definition
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  /// "OLS", "IV"
    str244 spec        ///
    str40  param       ///
    double coef se pval pre_mean rkf nobs /// <-- exactly five numeric columns
    using `out', replace



local specs "baseline rent hhi rent_hhi seniority rent_seniority hhi_seniority rent_hhi_seniority"


// Define OLS exogenous regressors by spec
local spec_ols_exog1  var4
local spec_ols_exog2  var4 var8 var9
local spec_ols_exog3  var4 var11 var12
local spec_ols_exog4  var4 var8 var9 var11 var12
local spec_ols_exog5  var4 var14 var15
local spec_ols_exog6  var4 var8 var9 var14 var15
local spec_ols_exog7  var4 var11 var12 var14 var15
local spec_ols_exog8  var4 var8 var9 var11 var12 var14 var15

// Define IV exogenous regressors by spec (drop the 3‐way terms)
local spec_iv_exog1   var4
local spec_iv_exog2   var4 var8
local spec_iv_exog3   var4 var11
local spec_iv_exog4   var4 var8 var11
local spec_iv_exog5   var4 var14
local spec_iv_exog6   var4 var8 var14
local spec_iv_exog7   var4 var11 var14
local spec_iv_exog8   var4 var8 var11 var14


// instruments by spec
local spec_instr1 var6 var7
local spec_instr2 var6 var7 var10
local spec_instr3 var6 var7 var13
local spec_instr4 var6 var7 var10 var13
local spec_instr5 var6 var7 var16
local spec_instr6 var6 var7 var10 var16
local spec_instr7 var6 var7 var13 var16
local spec_instr8 var6 var7 var10 var13 var16


// endogenous vars by spec
local spec_endo1  var3 var5
local spec_endo2  var3 var5 var9
local spec_endo3  var3 var5 var12
local spec_endo4  var3 var5 var9 var12
local spec_endo5  var3 var5 var15
local spec_endo6  var3 var5 var9 var15
local spec_endo7  var3 var5 var12 var15
local spec_endo8  var3 var5 var9 var12 var15


* ─── SPEC 1: Baseline on the full sample ────────────────────────
display as text "→ Spec 1: baseline (full sample)"

summarize growth_rate_we if covid == 0, meanonly
local pre_mean = r(mean)

// 1a) OLS
reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
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

// 1b) IV
ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id) savefirst
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

// 2) Restrict for mechanism specs
drop if missing(rent, hhi_1000, seniority_4)



// 4) Loop
forvalues i = 2/8 {
    // 1) pick the spec name
    local spec    : word `i' of `specs'

    // 2) build up the four pieces we need
    local ols_exog "`spec_ols_exog`i''"
    local iv_exog  "`spec_iv_exog`i''"
    local instr    "`spec_instr`i''"
    local endo     "`spec_endo`i''"
	

    display as text "→ Spec `i': `spec'"

    summarize growth_rate_we if covid == 0, meanonly
    local pre_mean = r(mean)

    // 4a) OLS
    reghdfe growth_rate_we var3 var5 `ols_exog', ///
        absorb(firm_id yh) vce(cluster firm_id)
	
	local N = e(N)  
	
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
       post handle ("OLS") ("`spec'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`N')
    }

    // 4b) IV
    ivreghdfe  growth_rate_we (`endo' = `instr') `iv_exog', ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
		
    local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
       post handle ("IV") ("`spec'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N')
    }

}

// 5) Close & export
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

display as result "→ CSV written to `result_dir'/consolidated_results.csv"
capture log close
