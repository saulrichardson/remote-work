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
* Productivity regressions controlling for endogenous role/seniority scaling
* Each specification controls for different composition changes
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Setup
*-----------------------------------------------------------------------------*

* Load user panel
use "$processed_data/user_panel_precovid.dta", clear
gen companyname_lower = lower(companyname)

* Keep observations with treatment
keep if !missing(var3, var5, var6, var7)

* Merge composition data (using simulated data for local testing)
merge m:1 companyname_lower using "$results/composition_role_seniority_simulated.dta", keep(match) nogen

* Get firm growth for endogenous controls
preserve
    use "$processed_data/firm_panel.dta", clear
    gen companyname_lower = lower(companyname)
    keep if yh >= 121  // Post-COVID
    collapse (mean) growth_post=growth_rate_we, by(companyname_lower)
    tempfile growth
    save `growth'
restore

merge m:1 companyname_lower using `growth', keep(match) nogen

* Create output file
capture postclose prod_results
tempfile results_out
postfile prod_results ///
    str40 composition_var str20 var_type ///
    double b3 se3 p3 ///
    double b5 se5 p5 ///
    double b3_comp se3_comp p3_comp ///
    double b5_comp se5_comp p5_comp ///
    double b3_growth se3_growth p3_growth ///
    double rkf long nobs ///
    using `results_out', replace

*-----------------------------------------------------------------------------*
* Part 1: Baseline (no composition controls)
*-----------------------------------------------------------------------------*

di _n "=== BASELINE SPECIFICATION ==="

ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local base_b3 = _b[var3]
local base_se3 = _se[var3]
local base_b5 = _b[var5]
local base_se5 = _se[var5]
local base_rkf = e(rkf)

di "Baseline Remote × Post: " %9.3f `base_b3' " (" %6.3f `base_se3' ")"
di "Baseline Remote × Post × Startup: " %9.3f `base_b5' " (" %6.3f `base_se5' ")"
di "KP F-stat: " %9.2f `base_rkf'

*-----------------------------------------------------------------------------*
* Part 2: Control for role composition (one at a time)
*-----------------------------------------------------------------------------*

di _n "=== CONTROLLING FOR ROLE COMPOSITION ==="

* Get role variables
ds pct_chg_soc*
local role_vars ""
foreach var of varlist pct_chg_soc* {
    if !strpos("`var'", "_") & "`var'" != "pct_chg_soc" {
        local role_vars "`role_vars' `var'"
    }
}

* Test top 5 roles
local count = 0
foreach comp_var of local role_vars {
    local count = `count' + 1
    if `count' > 5 continue, break
    
    di _n "Testing with control for " "`comp_var'" "..."
    
    * Create interactions
    gen var3_comp = var3 * `comp_var'
    gen var5_comp = var5 * `comp_var'
    gen var6_comp = var6 * `comp_var'
    gen var7_comp = var7 * `comp_var'
    
    * Create growth interactions
    gen var3_g = var3 * growth_post
    gen var5_g = var5 * growth_post
    gen var6_g = var6 * growth_post
    gen var7_g = var7 * growth_post
    
    * Run IV with composition and growth controls
    capture ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp var3_g var5_g = ///
         var6 var7 var6_comp var7_comp var6_g var7_g) ///
        var4 `comp_var' growth_post ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    if _rc == 0 {
        * Extract results
        post prod_results ("`comp_var'") ("role") ///
            (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
            (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
            (_b[var5_comp]) (_se[var5_comp]) (2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp]))) ///
            (_b[var3_g]) (_se[var3_g]) (2*ttail(e(df_r), abs(_b[var3_g]/_se[var3_g]))) ///
            (e(rkf)) (e(N))
        
        di "  Composition effect: " %9.3f _b[var3_comp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp])) ")"
        di "  Growth effect: " %9.3f _b[var3_g] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_g]/_se[var3_g])) ")"
    }
    
    drop var3_comp var5_comp var6_comp var7_comp var3_g var5_g var6_g var7_g
}

*-----------------------------------------------------------------------------*
* Part 3: Control for seniority composition
*-----------------------------------------------------------------------------*

di _n "=== CONTROLLING FOR SENIORITY COMPOSITION ==="

local seniority_vars "pct_chg_junior pct_chg_senior pct_chg_manager pct_chg_director"

foreach comp_var of local seniority_vars {
    * Check if variable exists
    capture confirm variable `comp_var'
    if _rc continue
    
    di _n "Testing with control for " "`comp_var'" "..."
    
    * Create interactions
    gen var3_comp = var3 * `comp_var'
    gen var5_comp = var5 * `comp_var'
    gen var6_comp = var6 * `comp_var'
    gen var7_comp = var7 * `comp_var'
    
    * Run IV
    capture ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
        var4 `comp_var' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    if _rc == 0 {
        post prod_results ("`comp_var'") ("seniority") ///
            (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
            (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
            (_b[var5_comp]) (_se[var5_comp]) (2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp]))) ///
            (0) (0) (0) ///
            (e(rkf)) (e(N))
        
        di "  Effect: " %9.3f _b[var3_comp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp])) ")"
    }
    
    drop var3_comp var5_comp var6_comp var7_comp
}

*-----------------------------------------------------------------------------*
* Part 4: Control for role × seniority
*-----------------------------------------------------------------------------*

di _n "=== CONTROLLING FOR ROLE × SENIORITY ==="

* Test key combinations
local key_combos "pct_chg_soc131051_senior pct_chg_soc132011_senior pct_chg_soc119111_manager"

foreach comp_var of local key_combos {
    capture confirm variable `comp_var'
    if _rc continue
    
    di _n "Testing " "`comp_var'" "..."
    
    * Create interactions
    gen var3_comp = var3 * `comp_var'
    gen var5_comp = var5 * `comp_var'
    gen var6_comp = var6 * `comp_var'
    gen var7_comp = var7 * `comp_var'
    
    * Run IV
    capture ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
        var4 `comp_var' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    if _rc == 0 {
        post prod_results ("`comp_var'") ("role_seniority") ///
            (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
            (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
            (_b[var5_comp]) (_se[var5_comp]) (2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp]))) ///
            (0) (0) (0) ///
            (e(rkf)) (e(N))
    }
    
    drop var3_comp var5_comp var6_comp var7_comp
}

*-----------------------------------------------------------------------------*
* Part 5: Summary
*-----------------------------------------------------------------------------*

postclose prod_results

* Load results
use `results_out', clear

di _n "=== SUMMARY OF COMPOSITION CONTROLS ==="

* Show significant composition effects
di _n "Significant composition interactions (p < 0.10):"
gsort p3_comp
list composition_var var_type b3_comp p3_comp if p3_comp < 0.10, sep(0)

* Compare to baseline
di _n "\nChange from baseline:"
gen change_b3 = b3 - `base_b3'
gen change_b5 = b5 - `base_b5'
format change_b3 change_b5 %9.3f

di _n "Average change in main effects when controlling for composition:"
table var_type, stat(mean change_b3 change_b5)

* Export results
export excel using "$results/productivity_role_seniority_results.xlsx", ///
    sheet("raw_results") firstrow(variables) replace

* Create summary table
preserve
    keep if p3_comp < 0.10 | p5_comp < 0.10
    keep composition_var var_type b3 b3_comp p3_comp b5 b5_comp p5_comp
    export excel using "$results/productivity_composition_summary.xlsx", ///
        sheet("significant") firstrow(variables) replace
restore

di _n "Analysis complete!"