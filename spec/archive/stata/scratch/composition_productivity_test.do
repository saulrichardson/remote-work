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
* Test productivity regressions with composition changes - Working Version
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Prepare user panel with composition
*-----------------------------------------------------------------------------*

* Load user panel
use "$processed_data/user_panel_precovid.dta", clear

* Create lowercase company name
gen companyname_lower = lower(companyname)

* Keep key variables and observations with treatment variation
keep if !missing(var3, var5, var6, var7)
keep user_id firm_id companyname companyname_lower yh total_contributions_q100 ///
     var3 var4 var5 var6 var7 startup covid

* Merge composition data
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen

* Check sample size
count
di "Matched observations: " r(N)

*-----------------------------------------------------------------------------*
* Part 2: Baseline productivity regression (no composition)
*-----------------------------------------------------------------------------*

di _n "=== BASELINE PRODUCTIVITY REGRESSION ==="

ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Store baseline results
local b3_base = _b[var3]
local se3_base = _se[var3]
local b5_base = _b[var5]
local se5_base = _se[var5]
local rkf_base = e(rkf)
local n_base = e(N)

di _n "Baseline results:"
di "Remote × Post: " %9.3f `b3_base' " (" %6.3f `se3_base' ")"
di "Remote × Post × Startup: " %9.3f `b5_base' " (" %6.3f `se5_base' ")"
di "KP F-stat: " %9.2f `rkf_base'

*-----------------------------------------------------------------------------*
* Part 3: Add composition interactions for top SOCs
*-----------------------------------------------------------------------------*

di _n "=== TESTING COMPOSITION INTERACTIONS ==="

* Focus on top 3 SOCs
local top_socs "pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191"

* Store results
postfile comp_results str20 soc ///
    double b3 se3 p3 ///
    double b5 se5 p5 ///
    double b3_comp se3_comp p3_comp ///
    double b5_comp se5_comp p5_comp ///
    double rkf long nobs ///
    using "$results/productivity_comp_results.dta", replace

foreach soc of local top_socs {
    di _n "Testing " "`soc'" "..."
    
    * Create interaction terms
    gen var3_comp = var3 * `soc'
    gen var5_comp = var5 * `soc'
    gen var6_comp = var6 * `soc'
    gen var7_comp = var7 * `soc'
    
    * Run IV regression
    capture ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
        var4 `soc' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    if _rc == 0 {
        * Extract results
        post comp_results ("`soc'") ///
            (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
            (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
            (_b[var5_comp]) (_se[var5_comp]) (2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp]))) ///
            (e(rkf)) (e(N))
            
        di "Remote × Post × " "`soc'" ": " %9.3f _b[var3_comp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp])) ")"
        di "Remote × Post × Startup × " "`soc'" ": " %9.3f _b[var5_comp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp])) ")"
    }
    else {
        di "Regression failed for " "`soc'"
    }
    
    drop var3_comp var5_comp var6_comp var7_comp
}

postclose comp_results

*-----------------------------------------------------------------------------*
* Part 4: Test with endogenous growth control
*-----------------------------------------------------------------------------*

di _n "=== WITH ENDOGENOUS GROWTH CONTROL ==="

* Get firm growth (simplified - using average growth)
preserve
    use "$processed_data/firm_panel.dta", clear
    gen companyname_lower = lower(companyname)
    keep if yh >= 121  // Post-COVID
    collapse (mean) growth_post=growth_rate_we, by(companyname_lower)
    tempfile growth
    save `growth'
restore

* Merge growth
merge m:1 companyname_lower using `growth', keep(match) nogen

* Create growth interactions
gen var3_g = var3 * growth_post
gen var5_g = var5 * growth_post
gen var6_g = var6 * growth_post
gen var7_g = var7 * growth_post

* Regression with growth control
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_g var5_g = var6 var7 var6_g var7_g) ///
    var4 growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "With growth control:"
di "Remote × Post: " %9.3f _b[var3] " (" %6.3f _se[var3] ")"
di "Remote × Post × Growth: " %9.3f _b[var3_g] " (" %6.3f _se[var3_g] ")"

*-----------------------------------------------------------------------------*
* Part 5: Display results summary
*-----------------------------------------------------------------------------*

di _n "=== RESULTS SUMMARY ==="

use "$results/productivity_comp_results.dta", clear
di _n "Composition interaction effects:"
list soc b3_comp p3_comp b5_comp p5_comp if p3_comp < 0.10 | p5_comp < 0.10

* Calculate average composition effects
sum b3_comp
local avg_b3_comp = r(mean)
sum b5_comp
local avg_b5_comp = r(mean)

di _n "Average interaction effects:"
di "Remote × Post × Composition: " %9.3f `avg_b3_comp'
di "Remote × Post × Startup × Composition: " %9.3f `avg_b5_comp'

di _n "Analysis complete!"