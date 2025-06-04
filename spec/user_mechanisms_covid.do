*============================================================*
* do/user_mechanisms_regressions.do
*  — Automated export of OLS, IV & first-stage F's
*    across 8 specification columns
*============================================================*

capture log close
// Canonical user mechanism regression script (wage included by default)
local specname   "user_mechanisms_covid"
log using "log/`specname'.log", replace text


// 0) Globals + setup
do "../src/globals.do"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load & prepare once
use "$processed_data/user_panel.dta", clear
gen seniority_4 = !inrange(seniority_levels,1,3)
// drop if missing(hhi_1000, seniority_4, rent)

// interactions
gen var8  = covid*rent
// gen   = covid*rent*remote
// gen  = teleworkable*covid*rent
gen var11 = covid*hhi_1000
// gen  = covid*hhi_1000*remote
// gen  = teleworkable*covid*hhi_1000
gen var14 = covid*seniority_4
// gen  = covid*seniority_4*remote
// gen  = teleworkable*covid*seniority_4


// pick your mechanism here
// local mech    sd_wage
// local mech_label  sdw 

local mech    p90_p10_gap
local mech_label  gap

// generate interactions
gen var17 = covid*`mech'
gen var18 = covid*`mech'*remote
gen var19 = teleworkable*covid*`mech'




capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  /// 
    str244 spec        ///
    str40  param       ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace



local specs ///
  "baseline" ///
  "rent" "hhi" "seniority" "`mech_label'" ///
  "rent_hhi" "rent_seniority" "rent_`mech_label'" "hhi_seniority" "hhi_`mech_label'" "seniority_`mech_label'" ///
  "rent_hhi_seniority" "rent_hhi_`mech_label'" "rent_seniority_`mech_label'" "hhi_seniority_`mech_label'" ///
  "rent_hhi_seniority_`mech_label'"


  
* ────────────────────────────────────────────────────────
* 3) Define spec_… locals for OLS exog, IV exog, instruments & endogenous
*    (indices correspond to word positions in `specs`)
* ────────────────────────────────────────────────────────

//  1) baseline
local spec_ols_exog1  var4
local spec_iv_exog1   var4
local spec_instr1     var6 var7
local spec_endo1      var3 var5

//  2) rent
local spec_ols_exog2  var4 var8  
local spec_iv_exog2   var4 var8
local spec_instr2     var6 var7 
local spec_endo2      var3 var5 

//  3) hhi
local spec_ols_exog3  var4 var11 
local spec_iv_exog3   var4 var11
local spec_instr3     var6 var7 
local spec_endo3      var3 var5 

//  4) seniority
local spec_ols_exog4  var4 var14 
local spec_iv_exog4   var4 var14
local spec_instr4     var6 var7 
local spec_endo4      var3 var5 

//  5) `mech'
local spec_ols_exog5  var4 var17 var18
local spec_iv_exog5   var4 var17
local spec_instr5     var6 var7 var19
local spec_endo5      var3 var5 var18

//  6) rent_hhi
local spec_ols_exog6  var4 var8  var11 
local spec_iv_exog6   var4 var8 var11
local spec_instr6     var6 var7  
local spec_endo6      var3 var5  

//  7) rent_seniority
local spec_ols_exog7  var4 var8  var14 
local spec_iv_exog7   var4 var8 var14
local spec_instr7     var6 var7  
local spec_endo7      var3 var5  

//  8) rent_`mech'
local spec_ols_exog8  var4 var8  var17 var18
local spec_iv_exog8   var4 var8 var17
local spec_instr8     var6 var7  var19
local spec_endo8      var3 var5  var18

//  9) hhi_seniority
local spec_ols_exog9  var4 var11  var14 
local spec_iv_exog9   var4 var11 var14
local spec_instr9     var6 var7  
local spec_endo9      var3 var5  

// 10) hhi_`mech'
local spec_ols_exog10 var4 var11  var17 var18
local spec_iv_exog10  var4 var11 var17
local spec_instr10    var6 var7  var19
local spec_endo10     var3 var5  var18

// 11) `mech'_seniority
local spec_ols_exog11 var4 var17 var18 var14 
local spec_iv_exog11  var4 var17 var14
local spec_instr11    var6 var7 var19 
local spec_endo11     var3 var5 var18 

// 12) rent_hhi_seniority
local spec_ols_exog12 var4 var8  var11  var14 
local spec_iv_exog12  var4 var8 var11 var14
local spec_instr12    var6 var7   
local spec_endo12     var3 var5   

// 13) rent_hhi_`mech'
local spec_ols_exog13 var4 var8  var11  var17 var18
local spec_iv_exog13  var4 var8 var11 var17
local spec_instr13    var6 var7   var19
local spec_endo13     var3 var5   var18

// 14) rent_seniority_`mech'
local spec_ols_exog14 var4 var8  var14  var17 var18
local spec_iv_exog14  var4 var8 var14 var17
local spec_instr14    var6 var7   var19
local spec_endo14     var3 var5   var18

// 15) hhi_seniority_`mech'
local spec_ols_exog15 var4 var11  var14  var17 var18
local spec_iv_exog15  var4 var11 var14 var17
local spec_instr15    var6 var7   var19
local spec_endo15     var3 var5   var18

// 16) rent_hhi_seniority_`mech'
local spec_ols_exog16 var4 var8  var11  var14  var17 var18
local spec_iv_exog16  var4 var8 var11 var14 var17
local spec_instr16    var6 var7    var19
local spec_endo16     var3 var5    var18



// drop if missing(rent, hhi_1000, seniority_4, sd_wage, p90_p10_gap)


// 3) SPEC 1: Baseline on the full sample
display as text "→ Spec 1: baseline (full sample)"

summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// 3a) OLS
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id user_id yh) vce(cluster user_id)
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

// 3b) IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id user_id yh) vce(cluster user_id) savefirst
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



// 4) Loop
forvalues i = 2/16 {
    // 1) pick the spec name
    local spec    : word `i' of `specs'

    // 2) build up the four pieces we need
    local ols_exog "`spec_ols_exog`i''"
    local iv_exog  "`spec_iv_exog`i''"
    local instr    "`spec_instr`i''"
    local endo     "`spec_endo`i''"
	

    display as text "→ Spec `i': `spec'"

    summarize total_contributions_q100 if covid == 0, meanonly
    local pre_mean = r(mean)

    // 4a) OLS
    reghdfe total_contributions_q100 var3 var5 `ols_exog', ///
        absorb(firm_id user_id yh) vce(cluster user_id)
	
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
    ivreghdfe total_contributions_q100 (`endo' = `instr') `iv_exog', ///
        absorb(firm_id user_id yh) vce(cluster user_id) savefirst
    local rkf = e(rkf)
	local N   = e(N)
	
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
