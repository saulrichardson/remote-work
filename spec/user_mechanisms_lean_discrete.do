*============================================================*
*  user_productivity_lean_discrete.do
*  — *Lean* user-productivity regressions with discrete Covid treatment.
*    • Allows switching between *full-remote* and *hybrid* definitions of
*      Covid treatment (var3 / var5) via a positional argument.
*    • Mirrors the specification structure of user_mechanisms_lean.do but
*      keeps the outcomes and fixed-effects set from user_productivity.do.
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse (optional) arguments
*    1) panel_variant : unbalanced | balanced | precovid   (default = precovid)
*    2) treat         : fullremote | hybrid               (default = hybrid)
* --------------------------------------------------------------------------

args panel_variant treat
if "`panel_variant'" == "" local panel_variant "precovid"
if "`treat'"         == "" local treat         "fullremote"

local specname "user_productivity_lean_`panel_variant'_`treat'"

capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text


// 1) Globals + setup ---------------------------------------------------------
do "../src/globals.do"

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"


// 2) Load user-level panel ---------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

// 2a) Overwrite var3 / var5 with requested discrete definitions -------------

if "`treat'" == "fullremote" {
    capture drop var3 var5
    gen var3 = var3_fullrem
    gen var5 = var5_fullrem
}
else if "`treat'" == "hybrid" {
    capture drop var3 var5
    gen var3 = var3_hybrid
    gen var5 = var5_hybrid
}
else {
    di as error "Unknown treat=`treat' — must be fullremote or hybrid"
    exit 1
}


// 3) Additional variables ----------------------------------------------------

gen seniority_4 = !inrange(seniority_levels,1,3)

// Interactions used by the lean mechanism spec (no teleworkable interactions)
gen var8  = covid*rent
gen var9  = covid*rent*startup
gen var11 = covid*hhi_1000
gen var12 = covid*hhi_1000*startup
gen var14 = covid*seniority_4
gen var15 = covid*seniority_4*startup

// Pick wage-dispersion mechanism
// (Same choices as elsewhere: sd_wage or p90_p10_gap)
local mech        p90_p10_gap
local mech_label  gap

gen var17 = covid*`mech'
gen var18 = covid*`mech'*startup


// 4) Postfile collector ------------------------------------------------------

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  ///
    str244 spec        ///
    str40  param       ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace


// 5) Specification list ------------------------------------------------------

local specs ///
  "baseline" ///
  "rent" "hhi" "seniority" "`mech_label'" ///
  "rent_hhi" "rent_seniority" "rent_`mech_label'" "hhi_seniority" "hhi_`mech_label'" "seniority_`mech_label'" ///
  "rent_hhi_seniority" "rent_hhi_`mech_label'" "rent_seniority_`mech_label'" "hhi_seniority_`mech_label'" ///
  "rent_hhi_seniority_`mech_label'"


// 6) Build spec-specific macro lists (OLS exog, IV exog, instruments, endog)

global BASE_ENDO "var3 var5"

//  1) baseline
local spec_ols_exog1  var4
local spec_iv_exog1   var4
local spec_instr1     var6 var7
local spec_endo1      $BASE_ENDO

//  2) rent
local spec_ols_exog2  var4 var8 var9
local spec_iv_exog2   var4 var8 var9
local spec_instr2     var6 var7
local spec_endo2      $BASE_ENDO

//  3) hhi
local spec_ols_exog3  var4 var11 var12
local spec_iv_exog3   var4 var11 var12
local spec_instr3     var6 var7
local spec_endo3      $BASE_ENDO

//  4) seniority
local spec_ols_exog4  var4 var14 var15
local spec_iv_exog4   var4 var14 var15
local spec_instr4     var6 var7
local spec_endo4      $BASE_ENDO

//  5) `mech'
local spec_ols_exog5  var4 var17 var18
local spec_iv_exog5   var4 var17 var18
local spec_instr5     var6 var7
local spec_endo5      $BASE_ENDO

//  6) rent_hhi
local spec_ols_exog6  var4 var8 var9 var11 var12
local spec_iv_exog6   var4 var8 var9 var11 var12
local spec_instr6     var6 var7
local spec_endo6      $BASE_ENDO

//  7) rent_seniority
local spec_ols_exog7  var4 var8 var9 var14 var15
local spec_iv_exog7   var4 var8 var9 var14 var15
local spec_instr7     var6 var7
local spec_endo7      $BASE_ENDO

//  8) rent_`mech'
local spec_ols_exog8  var4 var8 var9 var17 var18
local spec_iv_exog8   var4 var8 var9 var17 var18
local spec_instr8     var6 var7
local spec_endo8      $BASE_ENDO

//  9) hhi_seniority
local spec_ols_exog9  var4 var11 var12 var14 var15
local spec_iv_exog9   var4 var11 var12 var14 var15
local spec_instr9     var6 var7
local spec_endo9      $BASE_ENDO

// 10) hhi_`mech'
local spec_ols_exog10 var4 var11 var12 var17 var18
local spec_iv_exog10  var4 var11 var12 var17 var18
local spec_instr10    var6 var7
local spec_endo10     $BASE_ENDO

// 11) `mech'_seniority
local spec_ols_exog11 var4 var17 var18 var14 var15
local spec_iv_exog11  var4 var17 var18 var14 var15
local spec_instr11    var6 var7
local spec_endo11     $BASE_ENDO

// 12) rent_hhi_seniority
local spec_ols_exog12 var4 var8 var9 var11 var12 var14 var15
local spec_iv_exog12  var4 var8 var9 var11 var12 var14 var15
local spec_instr12    var6 var7
local spec_endo12     $BASE_ENDO

// 13) rent_hhi_`mech'
local spec_ols_exog13 var4 var8 var9 var11 var12 var17 var18
local spec_iv_exog13  var4 var8 var9 var11 var12 var17 var18
local spec_instr13    var6 var7
local spec_endo13     $BASE_ENDO

// 14) rent_seniority_`mech'
local spec_ols_exog14 var4 var8 var9 var14 var15 var17 var18
local spec_iv_exog14  var4 var8 var9 var14 var15 var17 var18
local spec_instr14    var6 var7
local spec_endo14     $BASE_ENDO

// 15) hhi_seniority_`mech'
local spec_ols_exog15 var4 var11 var12 var14 var15 var17 var18
local spec_iv_exog15  var4 var11 var12 var14 var15 var17 var18
local spec_instr15    var6 var7
local spec_endo15     $BASE_ENDO

// 16) rent_hhi_seniority_`mech'
local spec_ols_exog16 var4 var8 var9 var11 var12 var14 var15 var17 var18
local spec_iv_exog16  var4 var8 var9 var11 var12 var14 var15 var17 var18
local spec_instr16    var6 var7
local spec_endo16     $BASE_ENDO


// 7) Baseline spec ----------------------------------------------------------

display as text "→ Spec 1: baseline (full sample)"

summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// 7a) OLS
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(user_id#firm_id yh) vce(cluster user_id)
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

// 7b) IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(user_id#firm_id yh) vce(cluster user_id) savefirst
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


// 8) Loop over remaining specifications ------------------------------------

forvalues i = 2/16 {
    local spec    : word `i' of `specs'
    local ols_exog "`spec_ols_exog`i''"
    local iv_exog  "`spec_iv_exog`i''"
    local instr    "`spec_instr`i''"
    local endo     "`spec_endo`i''"

    display as text "→ Spec `i': `spec'"

    summarize total_contributions_q100 if covid == 0, meanonly
    local pre_mean = r(mean)

    // 8a) OLS
    reghdfe total_contributions_q100 var3 var5 `ols_exog', ///
        absorb(user_id#firm_id yh) vce(cluster user_id)
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

    // 8b) IV
    ivreghdfe total_contributions_q100 (`endo' = `instr') `iv_exog', ///
        absorb(user_id#firm_id yh) vce(cluster user_id) savefirst
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


// 9) Close & export ---------------------------------------------------------

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
capture log close
