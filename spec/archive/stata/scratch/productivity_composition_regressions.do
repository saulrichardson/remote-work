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

*=============================================================================*
* Productivity regressions controlling for endogenous composition changes
* Tests whether remote work effects vary by workforce composition shifts
*=============================================================================*

clear all
set more off

do "src/globals.do"

*-----------------------------------------------------------------------------*
* Productivity regression controlling for SOC composition changes
*-----------------------------------------------------------------------------*

use "$processed_data/user_panel_with_composition.dta", clear

* Create endogenous growth interactions with composition
gen g_c = growth_rate_we_post_c  // Post-COVID growth (endogenous)

* Store results
postfile results str32 specification str32 control_var ///
    double b3 double se3 double p3 ///
    double b5 double se5 double p5 ///
    double b_comp double se_comp double p_comp ///
    double rkf long nobs ///
    using "$results/productivity_composition_results.dta", replace

* Baseline (no composition controls)
ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

post results ("baseline") ("none") ///
    (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
    (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
    (.) (.) (.) ///
    (e(rkf)) (e(N))

* Control for overall growth (endogenous scaling)
gen var3_g = var3 * g_c
gen var5_g = var5 * g_c
gen var6_g = var6 * g_c
gen var7_g = var7 * g_c

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_g var5_g = var6 var7 var6_g var7_g) ///
    var4 g_c ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

post results ("growth_control") ("overall") ///
    (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
    (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
    (_b[var3_g]) (_se[var3_g]) (2*ttail(e(df_r), abs(_b[var3_g]/_se[var3_g]))) ///
    (e(rkf)) (e(N))

drop var3_g var5_g var6_g var7_g

* Loop through top SOC composition changes
foreach v of varlist pct_chg_soc* {
    local soc = substr("`v'", 13, .)
    
    * Check variation
    quietly sum `v'
    if r(sd) > 0 {
        * Create interactions with composition change
        gen var3_comp = var3 * `v'
        gen var5_comp = var5 * `v'
        gen var6_comp = var6 * `v'
        gen var7_comp = var7 * `v'
        
        * IV regression with composition controls
        capture ivreghdfe total_contributions_q100 ///
            (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
            var4 `v' g_c ///
            , absorb(firm_id#user_id yh) ///
            vce(cluster user_id)
            
        if _rc == 0 {
            post results ("soc_composition") ("`soc'") ///
                (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
                (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
                (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
                (e(rkf)) (e(N))
        }
        
        drop var3_comp var5_comp var6_comp var7_comp
    }
}

* Seniority concentration change
gen var3_sen = var3 * sen_concentration_chg
gen var5_sen = var5 * sen_concentration_chg
gen var6_sen = var6 * sen_concentration_chg
gen var7_sen = var7 * sen_concentration_chg

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_sen var5_sen = var6 var7 var6_sen var7_sen) ///
    var4 sen_concentration_chg g_c ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

post results ("seniority_composition") ("seniority") ///
    (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
    (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
    (_b[var3_sen]) (_se[var3_sen]) (2*ttail(e(df_r), abs(_b[var3_sen]/_se[var3_sen]))) ///
    (e(rkf)) (e(N))

postclose results

*-----------------------------------------------------------------------------*
* Format results table
*-----------------------------------------------------------------------------*

use "$results/productivity_composition_results.dta", clear
export delimited "$results/productivity_composition_results.csv", replace

* Display key findings
di _n "=== Productivity Effects by Composition Change ==="
list specification b3 se3 b5 se5 b_comp se_comp if inlist(specification, "baseline", "growth_control", "seniority_composition")

di "Productivity composition regressions completed"