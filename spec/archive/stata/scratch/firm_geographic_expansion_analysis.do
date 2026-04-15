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



*============================================================*
*  firm_geographic_expansion_analysis.do
*  — Test whether remote work enables geographic expansion
*    Follows firm_scaling.do framework
*============================================================*

// 0) Setup environment
do "../globals.do"

// Setup logging
local specname "firm_geographic_expansion_analysis"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load firm panel (standard panel with treatment variables)
use "$processed_data/firm_panel.dta", clear

di _n "=== Loading and Merging Geographic Expansion Data ===" _n
di "Initial firm panel: " _N " observations"

// 2) Merge geographic expansion metrics
preserve
    import delimited "$processed_data/firm_geographic_expansion.csv", clear
    
    // Check the data
    di "Geographic expansion data: " _N " observations"
    sum share_new_geo, detail
    
    // Standardize firm name
    rename firm companyname
    replace companyname = lower(companyname)
    
    tempfile geo_expansion
    save `geo_expansion'
restore

// Standardize firm name in panel
replace companyname = lower(companyname)

// Merge
merge 1:1 companyname yh using `geo_expansion', keep(1 3) gen(geo_merge)

di _n "Merge results:"
tab geo_merge

// 3) Check the key variables exist
di _n "=== Checking Key Variables ===" _n

// Check treatment variables
foreach v in var3 var5 var4 var6 var7 remote teleworkable covid {
    capture confirm variable `v'
    if _rc {
        di "WARNING: Variable `v' not found"
    }
    else {
        qui sum `v'
        di "`v' exists: N=" r(N) " mean=" %6.3f r(mean) " sd=" %6.3f r(sd)
    }
}

// Check outcome
qui sum share_new_geo
di _n "share_new_geo: N=" r(N) " mean=" %6.3f r(mean) " sd=" %6.3f r(sd)

// 4) Summary statistics
di _n "=== Summary Statistics for Geographic Expansion ===" _n

// Overall
sum share_new_geo total_hires n_new_locations if geo_merge == 3

// By period
di _n "By COVID period:"
table covid if geo_merge == 3, contents(mean share_new_geo n share_new_geo)

// By remote status (if available)
capture confirm variable remote
if !_rc {
    di _n "By remote status (post-COVID):"
    table remote if covid == 1 & geo_merge == 3, contents(mean share_new_geo n share_new_geo)
}

// 5) Prepare for regressions
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome    ///
    str40  param      ///
    double coef se pval pre_mean ///
    double rkf nobs   ///
    using `out', replace

// First-stage file
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

// 6) Main regressions
di _n "=== Running Main Regressions ===" _n

// Check if we have enough variation
qui sum share_new_geo if !missing(var3, var5, var4) & geo_merge == 3
local N_withdata = r(N)
di "Observations with geographic data and treatment vars: " `N_withdata'

if `N_withdata' > 100 {
    
    // Pre-period mean (should be 0 or missing for this outcome)
    qui sum share_new_geo if covid == 0 & geo_merge == 3
    local pre_mean = r(mean)
    di "Pre-period mean: " %6.3f `pre_mean'
    
    // --- OLS ---
    di _n "Running OLS..."
    reghdfe share_new_geo var3 var5 var4 if geo_merge == 3, ///
        absorb(firm_id yh) vce(cluster firm_id)
    
    local N_ols = e(N)
    di "OLS N = " `N_ols'
    
    // Store OLS results
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle ("OLS") ("share_new_geo") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N_ols')
    }
    
    // --- IV ---
    di _n "Running IV..."
    ivreghdfe share_new_geo (var3 var5 = var6 var7) var4 if geo_merge == 3, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    
    local rkf = e(rkf)
    local N_iv = e(N)
    di "IV N = " `N_iv'
    di "Kleibergen-Paap rk F = " %6.2f `rkf'
    
    // Store IV results  
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle ("IV") ("share_new_geo") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N_iv')
    }
    
    // Store first-stage results
    matrix FS = e(first)
    local F3 = FS[4,1]
    local F5 = FS[4,2]
    
    // var3 first stage
    estimates restore _ivreg2_var3
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle_fs ("var3") ("`p'") ///
            (`b') (`se') (`pval') ///
            (`F3') (`rkf') (`N_fs')
    }
    
    // var5 first stage
    estimates restore _ivreg2_var5
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle_fs ("var5") ("`p'") ///
            (`b') (`se') (`pval') ///
            (`F5') (`rkf') (`N_fs')
    }
}
else {
    di "ERROR: Not enough observations with complete data"
}

// 7) Alternative specifications for robustness
di _n "=== Robustness Checks ===" _n

// Intensive margin only (exclude zero-hire periods)
di "Intensive margin (total_hires > 0):"
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4 ///
    if geo_merge == 3 & total_hires > 0, ///
    absorb(firm_id yh) vce(cluster firm_id)

// Extensive margin - any new geography
gen any_new_geo = (n_new_locations > 0) if geo_merge == 3
di _n "Extensive margin (any new geography):"
ivreghdfe any_new_geo (var3 var5 = var6 var7) var4 if geo_merge == 3, ///
    absorb(firm_id yh) vce(cluster firm_id)

// Count of new locations
di _n "Count of new locations entered:"
ivreghdfe n_new_locations (var3 var5 = var6 var7) var4 if geo_merge == 3, ///
    absorb(firm_id yh) vce(cluster firm_id)

// 8) Export results
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

postclose handle_fs  
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", replace

// 9) Display summary
di _n "==========================================="
di "SUMMARY OF KEY RESULTS"
di "==========================================="

use `out', clear
keep if model_type == "IV" & param == "var3" & outcome == "share_new_geo"
if _N > 0 {
    local coef = coef[1]
    local se = se[1]
    local pval = pval[1]
    
    di _n "Main IV estimate (var3 on share_new_geo):"
    di "  Coefficient: " %7.4f `coef' 
    di "  Std Error: " %7.4f `se'
    di "  P-value: " %6.4f `pval'
    
    if `pval' < 0.10 {
        di _n "Result: Remote work " cond(`coef' > 0, "increases", "decreases") ///
            " geographic expansion"
        di "Effect size: " %4.1f abs(`coef'*100) " percentage points"
    }
    else {
        di _n "Result: No statistically significant effect on geographic expansion"
    }
}

log close
di _n "Results saved to: `result_dir'/consolidated_results.csv"
