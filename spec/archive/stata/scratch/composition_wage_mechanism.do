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
* Test productivity with composition changes AND wage inequality mechanisms
* Combines composition analysis with wage gap mechanisms from other specs
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Load and merge all data sources
*-----------------------------------------------------------------------------*

* Load user panel
use "$processed_data/user_panel_precovid.dta", clear

* Create lowercase company name
gen companyname_lower = lower(companyname)

* Keep key variables
keep if !missing(var3, var5, var6, var7)
keep user_id firm_id companyname companyname_lower yh total_contributions_q100 ///
     var3 var4 var5 var6 var7 startup covid

* Merge composition data
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen

* Get wage inequality from firm panel
preserve
    use "$processed_data/firm_panel.dta", clear
    gen companyname_lower = lower(companyname)
    keep companyname_lower p90_p10_gap sd_wage
    * Keep last observation per firm
    bysort companyname_lower: keep if _n == _N
    tempfile wage_data
    save `wage_data'
restore

merge m:1 companyname_lower using `wage_data', keep(match) nogen

* Check sample
count
di "Analysis sample: " r(N) " observations"

*-----------------------------------------------------------------------------*
* Part 2: Create mechanism interactions
*-----------------------------------------------------------------------------*

* Standardize wage gap measure
sum p90_p10_gap
gen wage_gap_std = (p90_p10_gap - r(mean)) / r(sd)

* Create wage mechanism interactions
gen var17 = covid * wage_gap_std
gen var18 = covid * wage_gap_std * startup

*-----------------------------------------------------------------------------*
* Part 3: Test composition + wage gap jointly
*-----------------------------------------------------------------------------*

di _n "=== COMPOSITION + WAGE GAP ANALYSIS ==="

* Focus on top SOCs that showed significant effects
local key_socs "pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191"

* Store results
capture postclose comp_wage
tempfile results_out
postfile comp_wage str20 soc ///
    double b3 se3 p3 ///
    double b5 se5 p5 ///
    double b3_comp se3_comp p3_comp ///
    double b5_comp se5_comp p5_comp ///
    double b17 se17 p17 ///
    double b18 se18 p18 ///
    double rkf long nobs ///
    using `results_out', replace

foreach soc of local key_socs {
    di _n "Testing " "`soc'" " with wage gap..."
    
    * Create composition interactions
    gen var3_comp = var3 * `soc'
    gen var5_comp = var5 * `soc'
    gen var6_comp = var6 * `soc'
    gen var7_comp = var7 * `soc'
    
    * Run IV regression with both mechanisms
    capture ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
        var4 `soc' var17 var18 ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    if _rc == 0 {
        * Extract all coefficients
        post comp_wage ("`soc'") ///
            (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
            (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
            (_b[var5_comp]) (_se[var5_comp]) (2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp]))) ///
            (_b[var17]) (_se[var17]) (2*ttail(e(df_r), abs(_b[var17]/_se[var17]))) ///
            (_b[var18]) (_se[var18]) (2*ttail(e(df_r), abs(_b[var18]/_se[var18]))) ///
            (e(rkf)) (e(N))
            
        di "Key results:"
        di "  Remote × Post × " "`soc'" ": " %9.3f _b[var3_comp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp])) ")"
        di "  Remote × Post × Wage Gap: " %9.3f _b[var17] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var17]/_se[var17])) ")"
    }
    
    drop var3_comp var5_comp var6_comp var7_comp
}

postclose comp_wage

*-----------------------------------------------------------------------------*
* Part 4: Test triple interaction (composition × wage gap)
*-----------------------------------------------------------------------------*

di _n "=== TRIPLE INTERACTION: COMPOSITION × WAGE GAP ==="

* Pick the most significant composition change
local main_soc "pct_chg_soc1320"  // Finance managers

* Create all interactions
gen double comp_wage = `main_soc' * wage_gap_std
gen var3_cw = var3 * comp_wage
gen var5_cw = var5 * comp_wage
gen var6_cw = var6 * comp_wage 
gen var7_cw = var7 * comp_wage

* Also need the double interactions
gen var3_c = var3 * `main_soc'
gen var5_c = var5 * `main_soc'
gen var6_c = var6 * `main_soc'
gen var7_c = var7 * `main_soc'

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_c var5_c var3_cw var5_cw = ///
     var6 var7 var6_c var7_c var6_cw var7_cw) ///
    var4 `main_soc' var17 var18 wage_gap_std comp_wage ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "Triple interaction results:"
di "Remote × Post × Composition × Wage Gap: " %9.3f _b[var3_cw] " (" %6.3f _se[var3_cw] ")"
di "Remote × Post × Startup × Comp × Wage: " %9.3f _b[var5_cw] " (" %6.3f _se[var5_cw] ")"

*-----------------------------------------------------------------------------*
* Part 5: Summary and interpretation
*-----------------------------------------------------------------------------*

di _n "=== SUMMARY ==="

* Load and display results
use `results_out', clear
di _n "Composition and wage gap interaction effects:"
list soc b3_comp p3_comp b17 p17 if p3_comp < 0.10 | p17 < 0.10

* Calculate correlations
use "$processed_data/user_panel_precovid.dta", clear
gen companyname_lower = lower(companyname)
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen
merge m:1 companyname_lower using `wage_data', keep(match) nogen

collapse (first) pct_chg_soc* p90_p10_gap, by(companyname_lower)

di _n "Correlation between composition changes and wage inequality:"
pwcorr pct_chg_soc1320 pct_chg_soc1191 p90_p10_gap, star(0.05)

di _n "Analysis complete!"