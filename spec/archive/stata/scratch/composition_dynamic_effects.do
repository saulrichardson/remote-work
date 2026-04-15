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
* Test dynamic/time-varying composition effects
* Allows composition effects to vary by half-year post-COVID
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Prepare productivity panel with composition
*-----------------------------------------------------------------------------*

use "$processed_data/user_panel_precovid.dta", clear

* Create lowercase company name
gen companyname_lower = lower(companyname)

* Keep key variables
keep if !missing(var3, var5, var6, var7)
keep user_id firm_id companyname companyname_lower yh total_contributions_q100 ///
     var3 var4 var5 var6 var7 startup covid

* Merge composition data
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen

* Create post-COVID period indicators
gen post1 = (yh == 121)  // 2020H1
gen post2 = (yh == 122)  // 2020H2
gen post3 = (yh == 123)  // 2021H1
gen post4 = (yh == 124)  // 2021H2

*-----------------------------------------------------------------------------*
* Part 2: Create time-varying treatment and instruments
*-----------------------------------------------------------------------------*

* For each post period, create separate treatment variables
foreach p in 1 2 3 4 {
    * Base treatments
    gen var3_p`p' = var3 * post`p'
    gen var5_p`p' = var5 * post`p'
    gen var6_p`p' = var6 * post`p'
    gen var7_p`p' = var7 * post`p'
}

*-----------------------------------------------------------------------------*
* Part 3: Dynamic effects for key SOCs
*-----------------------------------------------------------------------------*

di _n "=== DYNAMIC COMPOSITION EFFECTS ==="

* Focus on SOCs with significant baseline effects
local key_socs "pct_chg_soc1320 pct_chg_soc1191"  // Finance & Management

* Store dynamic results
capture postclose dynamic
tempfile dynamic_out
postfile dynamic str20 soc int period ///
    double b3 se3 p3 ///
    double b5 se5 p5 ///
    double b3_comp se3_comp p3_comp ///
    double b5_comp se5_comp p5_comp ///
    using `dynamic_out', replace

foreach soc of local key_socs {
    di _n "Testing dynamic effects for " "`soc'" "..."
    
    * Create time-varying composition interactions
    foreach p in 1 2 3 4 {
        gen var3_p`p'_comp = var3_p`p' * `soc'
        gen var5_p`p'_comp = var5_p`p' * `soc'
        gen var6_p`p'_comp = var6_p`p' * `soc'
        gen var7_p`p'_comp = var7_p`p' * `soc'
    }
    
    * Run IV with all periods
    ivreghdfe total_contributions_q100 ///
        (var3_p1 var5_p1 var3_p1_comp var5_p1_comp ///
         var3_p2 var5_p2 var3_p2_comp var5_p2_comp ///
         var3_p3 var5_p3 var3_p3_comp var5_p3_comp ///
         var3_p4 var5_p4 var3_p4_comp var5_p4_comp = ///
         var6_p1 var7_p1 var6_p1_comp var7_p1_comp ///
         var6_p2 var7_p2 var6_p2_comp var7_p2_comp ///
         var6_p3 var7_p3 var6_p3_comp var7_p3_comp ///
         var6_p4 var7_p4 var6_p4_comp var7_p4_comp) ///
        var4 `soc' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    * Extract period-specific effects
    foreach p in 1 2 3 4 {
        post dynamic ("`soc'") (`p') ///
            (_b[var3_p`p']) (_se[var3_p`p']) (2*ttail(e(df_r), abs(_b[var3_p`p']/_se[var3_p`p']))) ///
            (_b[var5_p`p']) (_se[var5_p`p']) (2*ttail(e(df_r), abs(_b[var5_p`p']/_se[var5_p`p']))) ///
            (_b[var3_p`p'_comp]) (_se[var3_p`p'_comp]) (2*ttail(e(df_r), abs(_b[var3_p`p'_comp]/_se[var3_p`p'_comp]))) ///
            (_b[var5_p`p'_comp]) (_se[var5_p`p'_comp]) (2*ttail(e(df_r), abs(_b[var5_p`p'_comp]/_se[var5_p`p'_comp])))
    }
    
    * Clean up
    drop var3_p*_comp var5_p*_comp var6_p*_comp var7_p*_comp
}

postclose dynamic

*-----------------------------------------------------------------------------*
* Part 4: Test pre-trends (placebo)
*-----------------------------------------------------------------------------*

di _n "=== PRE-TREND TEST ==="

* Create pre-COVID period indicators
gen pre1 = (yh == 117)  // 2018H1
gen pre2 = (yh == 118)  // 2018H2
gen pre3 = (yh == 119)  // 2019H1

* Focus on one key SOC
local test_soc "pct_chg_soc1320"

* Create pre-period interactions
foreach p in 1 2 3 {
    gen var3_pre`p' = var3 * pre`p'
    gen var5_pre`p' = var5 * pre`p'
    gen var6_pre`p' = var6 * pre`p'
    gen var7_pre`p' = var7 * pre`p'
    
    gen var3_pre`p'_comp = var3_pre`p' * `test_soc'
    gen var5_pre`p'_comp = var5_pre`p' * `test_soc'
    gen var6_pre`p'_comp = var6_pre`p' * `test_soc'
    gen var7_pre`p'_comp = var7_pre`p' * `test_soc'
}

* Test pre-trends
ivreghdfe total_contributions_q100 ///
    (var3_pre1 var5_pre1 var3_pre1_comp var5_pre1_comp ///
     var3_pre2 var5_pre2 var3_pre2_comp var5_pre2_comp ///
     var3_pre3 var5_pre3 var3_pre3_comp var5_pre3_comp = ///
     var6_pre1 var7_pre1 var6_pre1_comp var7_pre1_comp ///
     var6_pre2 var7_pre2 var6_pre2_comp var7_pre2_comp ///
     var6_pre3 var7_pre3 var6_pre3_comp var7_pre3_comp) ///
    var4 `test_soc' ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "Pre-trend test for composition interactions:"
foreach p in 1 2 3 {
    di "Period -" (4-`p') ": b = " %9.3f _b[var3_pre`p'_comp] ///
       " (p = " %6.4f 2*ttail(e(df_r), abs(_b[var3_pre`p'_comp]/_se[var3_pre`p'_comp])) ")"
}

*-----------------------------------------------------------------------------*
* Part 5: Visualize dynamic effects
*-----------------------------------------------------------------------------*

di _n "=== PREPARING VISUALIZATION DATA ==="

use `dynamic_out', clear

* Reshape for plotting
reshape wide b3 se3 p3 b5 se5 p5 b3_comp se3_comp p3_comp b5_comp se5_comp p5_comp, ///
    i(soc) j(period)

* Create period labels
gen period_label = ""
replace period_label = "2020H1" if _n == 1
replace period_label = "2020H2" if _n == 2  
replace period_label = "2021H1" if _n == 3
replace period_label = "2021H2" if _n == 4

* Export for plotting
export delimited using "$results/dynamic_composition_effects.csv", replace

di _n "Results saved to: $results/dynamic_composition_effects.csv"

*-----------------------------------------------------------------------------*
* Part 6: Summary statistics by period
*-----------------------------------------------------------------------------*

di _n "=== SUMMARY BY PERIOD ==="

* Show average effects by period
di _n "Average composition interaction effects by period:"
list soc b3_comp1 b3_comp2 b3_comp3 b3_comp4

* Test for increasing/decreasing trend
di _n "Testing for time trends in effects..."
foreach i in 1 2 3 4 {
    gen period`i' = (`i')
    gen effect`i' = b3_comp`i'
}

reshape long period effect, i(soc) j(time)
reg effect period, cluster(soc)

di _n "Time trend coefficient: " %9.3f _b[period] " (p = " %6.4f 2*ttail(e(df_r), abs(_b[period]/_se[period])) ")"

di _n "Analysis complete!"