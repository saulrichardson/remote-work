*============================================================*
*  user_mechanisms_binned.do
*  — Horse-race mechanisms identical to user_mechanisms.do but continuous
*    mechanism variables are binarised (High=1 if > median).
*============================================================*

capture log close
cap mkdir "log"

* 0) Optional panel variant argument (default: precovid) -------------
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname "user_mechanisms_binned_`panel_variant'"
log using "log/`specname'.log", replace text

// ---------------------------------------------------------------------
// 1) Globals & directories
// ---------------------------------------------------------------------
do "../src/globals.do"
local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

// ---------------------------------------------------------------------
// 2) Load panel and create HIGH/LOW dummies ---------------------------
// ---------------------------------------------------------------------

use "$processed_data/user_panel_`panel_variant'.dta", clear

* Seniority dummy (already binary but re-create for robustness)
gen seniority_4 = !inrange(seniority_levels,1,3)

foreach v in rent hhi_1000 p90_p10_gap {
//     if !_rc {
        quietly summarize `v', detail
        scalar med_`v' = r(p50)
        gen `v'_hi = (`v' > med_`v') if !missing(`v')
        replace `v'_hi = . if missing(`v')
        drop `v'
        rename `v'_hi `v'
//     }
}

// ---------------------------------------------------------------------
// 3) Interaction terms (identical structure to original script)
// ---------------------------------------------------------------------

gen var8  = covid*rent
gen var9  = covid*rent*remote
gen var10 = teleworkable*covid*rent
gen var11 = covid*hhi_1000
gen var12 = covid*hhi_1000*remote
gen var13 = teleworkable*covid*hhi_1000
gen var14 = covid*seniority_4
gen var15 = covid*seniority_4*remote
gen var16 = teleworkable*covid*seniority_4

local mech       p90_p10_gap
local mech_label gap

gen var17 = covid*`mech'
gen var18 = covid*`mech'*remote
gen var19 = teleworkable*covid*`mech'

// ---------------------------------------------------------------------
// 4) Postfile setup & spec definitions (copied from original)
// ---------------------------------------------------------------------

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

// --- Spec matrices ------------------------------------------------------

//  1) baseline
local spec_ols_exog1  var4
local spec_iv_exog1   var4
local spec_instr1     var6 var7
local spec_endo1      var3 var5

//  2) rent
local spec_ols_exog2  var4 var8 var9
local spec_iv_exog2   var4 var8
local spec_instr2     var6 var7 var10
local spec_endo2      var3 var5 var9

//  3) hhi
local spec_ols_exog3  var4 var11 var12
local spec_iv_exog3   var4 var11
local spec_instr3     var6 var7 var13
local spec_endo3      var3 var5 var12

//  4) seniority
local spec_ols_exog4  var4 var14 var15
local spec_iv_exog4   var4 var14
local spec_instr4     var6 var7 var16
local spec_endo4      var3 var5 var15

//  5) `mech'
local spec_ols_exog5  var4 var17 var18
local spec_iv_exog5   var4 var17
local spec_instr5     var6 var7 var19
local spec_endo5      var3 var5 var18

//  6) rent_hhi
local spec_ols_exog6  var4 var8 var9 var11 var12
local spec_iv_exog6   var4 var8 var11
local spec_instr6     var6 var7 var10 var13
local spec_endo6      var3 var5 var9 var12

//  7) rent_seniority
local spec_ols_exog7  var4 var8 var9 var14 var15
local spec_iv_exog7   var4 var8 var14
local spec_instr7     var6 var7 var10 var16
local spec_endo7      var3 var5 var9 var15

//  8) rent_`mech'
local spec_ols_exog8  var4 var8 var9 var17 var18
local spec_iv_exog8   var4 var8 var17
local spec_instr8     var6 var7 var10 var19
local spec_endo8      var3 var5 var9 var18

//  9) hhi_seniority
local spec_ols_exog9  var4 var11 var12 var14 var15
local spec_iv_exog9   var4 var11 var14
local spec_instr9     var6 var7 var13 var16
local spec_endo9      var3 var5 var12 var15

// 10) hhi_`mech'
local spec_ols_exog10 var4 var11 var12 var17 var18
local spec_iv_exog10  var4 var11 var17
local spec_instr10    var6 var7 var13 var19
local spec_endo10     var3 var5 var12 var18

// 11) `mech'_seniority
local spec_ols_exog11 var4 var17 var18 var14 var15
local spec_iv_exog11  var4 var17 var14
local spec_instr11    var6 var7 var19 var16
local spec_endo11     var3 var5 var18 var15

// 12) rent_hhi_seniority
local spec_ols_exog12 var4 var8 var9 var11 var12 var14 var15
local spec_iv_exog12  var4 var8 var11 var14
local spec_instr12    var6 var7 var10 var13 var16
local spec_endo12     var3 var5 var9 var12 var15

// 13) rent_hhi_`mech'
local spec_ols_exog13 var4 var8 var9 var11 var12 var17 var18
local spec_iv_exog13  var4 var8 var11 var17
local spec_instr13    var6 var7 var10 var13 var19
local spec_endo13     var3 var5 var9 var12 var18

// 14) rent_seniority_`mech'
local spec_ols_exog14 var4 var8 var9 var14 var15 var17 var18
local spec_iv_exog14  var4 var8 var14 var17
local spec_instr14    var6 var7 var10 var16 var19
local spec_endo14     var3 var5 var9 var15 var18

// 15) hhi_seniority_`mech'
local spec_ols_exog15 var4 var11 var12 var14 var15 var17 var18
local spec_iv_exog15  var4 var11 var14 var17
local spec_instr15    var6 var7 var13 var16 var19
local spec_endo15     var3 var5 var12 var15 var18

// 16) rent_hhi_seniority_`mech'
local spec_ols_exog16 var4 var8 var9 var11 var12 var14 var15 var17 var18
local spec_iv_exog16  var4 var8 var11 var14 var17
local spec_instr16    var6 var7 var10 var13 var16 var19
local spec_endo16     var3 var5 var9 var12 var15 var18

// ---------------------------------------------------------------------
// 5) Run regressions ----------------------------------------------------
// ---------------------------------------------------------------------

display as text "→ Spec 1: baseline (full sample)"
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

*------------------ OLS
reghdfe total_contributions_q100 var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs((_b[`p']/ _se[`p'])) )
    post handle ("OLS") ("baseline") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
}

*------------------ IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N = e(N)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs((_b[`p']/ _se[`p'])) )
    post handle ("IV") ("baseline") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
}

// Loop remaining specs
forvalues i = 2/16 {
    local spec : word `i' of `specs'
    local ols_exog "`spec_ols_exog`i''"
    local iv_exog  "`spec_iv_exog`i''"
    local instr    "`spec_instr`i''"
    local endo     "`spec_endo`i''"

    display as text "→ Spec `i': `spec'"
    summarize total_contributions_q100 if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
    reghdfe total_contributions_q100 var3 var5 `ols_exog', absorb(firm_id#user_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 {
        local b = _b[`p']
        local se = _se[`p']
        local pval = 2*ttail(e(df_r), abs((_b[`p']/ _se[`p'])) )
        post handle ("OLS") ("`spec'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    // IV
    ivreghdfe total_contributions_q100 (`endo' = `instr') `iv_exog', absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 {
        local b = _b[`p']
        local se = _se[`p']
        local pval = 2*ttail(e(df_r), abs((_b[`p']/ _se[`p'])) )
        post handle ("IV") ("`spec'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }
}

// ---------------------------------------------------------------------
// 6) Export -------------------------------------------------------------
// ---------------------------------------------------------------------

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

display as result "→ CSV written to `result_dir'/consolidated_results.csv"
capture log close
