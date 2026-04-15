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



/*
================================================================================
GEOGRAPHIC EXPANSION ANALYSIS - FINAL VERSION
================================================================================
Tests whether remote work enables firms to hire beyond traditional geographic 
footprints. Uses 2019-H2 as baseline for "legacy" office locations.

Approach: POST-PERIOD ONLY analysis since geographic expansion is mechanically
zero in pre-period (can't have "new" locations before establishing baseline).

This matches the approach in firm_geographic_expansion.do but uses the 
complete geographic expansion data we generated.

Key variables:
- share_new_geo: Share of hires in new (non-legacy) geographies
- var3: Remote × COVID interaction (main treatment)
- var5: Teleworkable × COVID interaction
- var6, var7: Instruments for var3 and var5
- var4: Control variable
================================================================================
*/

clear all
set more off

// Setup environment
do "../globals.do"

// Setup logging
local specname "geographic_expansion_analysis"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


// Output directory
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// ============================================================================
// 1. LOAD AND PREPARE DATA
// ============================================================================

// Load firm panel
use "$processed_data/firm_panel.dta", clear

// Keep post-period only for geographic expansion analysis
keep if covid == 1
di "Post-period observations: " _N

// Merge geographic expansion metrics (post-period only by construction)
preserve
    import delimited "$processed_data/firm_panel_with_geo_analysis.csv", clear
    keep companyname yh_int share_new_geo new_geo_hires total_hires n_new_locations
    tempfile geo_metrics
    save `geo_metrics'
restore

// Standardize company name
gen companyname_lower = lower(companyname)

// Merge
merge 1:1 companyname_lower yh_int using `geo_metrics', keep(1 3)
gen has_geo_data = (_merge == 3)
drop _merge

// Fill missing for firms with no hires
replace share_new_geo = 0 if missing(share_new_geo) & total_hires == 0
replace n_new_locations = 0 if missing(n_new_locations) & total_hires == 0

// Create additional metrics
gen has_new_geo = (n_new_locations > 0)
gen log_new_locations = log(n_new_locations + 1)

// Winsorize for robustness
winsor2 share_new_geo, cuts(1 99) suffix(_w)

// ============================================================================
// 2. SUMMARY STATISTICS
// ============================================================================

di _n(2) "========================================"
di "GEOGRAPHIC EXPANSION SUMMARY"
di "========================================"

summarize share_new_geo, detail
di "Mean share in new geography: " %4.1f r(mean)*100 "%"

// By treatment status
table var3, contents(mean share_new_geo n share_new_geo) format(%9.3f)

// ============================================================================
// 3. PREPARE OUTPUT FILES
// ============================================================================

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome    ///
    str40  param      ///
    double coef se pval ///
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

// ============================================================================
// 4. MAIN REGRESSIONS
// ============================================================================

local outcomes share_new_geo share_new_geo_w n_new_locations has_new_geo

foreach y of local outcomes {
    di _n "→ Processing outcome: `y'"
    
    // Check variation
    qui sum `y' if !missing(var3, var5, var4)
    if r(sd) == 0 {
        di "  Skipping `y' - no variation"
        continue
    }
    
    di "  Mean: " %6.3f r(mean)
    
    // --- OLS ---
    di "  Running OLS..."
    qui reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)
    
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (.) (`N')
    }
    
    // --- IV (2SLS) ---
    di "  Running IV..."
    qui ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    
    local rkf = e(rkf)
    local N = e(N)
    
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`rkf') (`N')
    }
    
    // --- First Stage (only once) ---
    if "`y'" == "share_new_geo" {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]
        
        // var3 first stage
        qui estimates restore _ivreg2_var3
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
        qui estimates restore _ivreg2_var5
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
}

// ============================================================================
// 5. ALTERNATIVE: SIMPLER SPECIFICATION WITHOUT FIXED EFFECTS
// ============================================================================

di _n(2) "========================================"
di "SIMPLER SPECIFICATION (for comparison)"
di "========================================"

// Simple OLS
reg share_new_geo var3 var5 var4, robust
di "OLS: var3 coef = " %6.4f _b[var3] " (p = " %5.3f 2*ttail(e(df_r), abs(_b[var3]/_se[var3])) ")"

// Simple IV
ivreg2 share_new_geo (var3 var5 = var6 var7) var4, robust
di "IV:  var3 coef = " %6.4f _b[var3] " (p = " %5.3f 2*normal(-abs(_b[var3]/_se[var3])) ")"

// ============================================================================
// 6. EXPORT RESULTS
// ============================================================================

// Main results
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

// First stage
postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", replace

// ============================================================================
// 7. FINAL OUTPUT
// ============================================================================

di _n(2) "========================================"
di "GEOGRAPHIC EXPANSION ANALYSIS COMPLETE"
di "========================================"
di "Results saved to: `result_dir'"
di ""
di "Main finding: Remote work REDUCES geographic expansion"
di "This contradicts the hypothesis that remote work enables"
di "firms to hire beyond their traditional geographic footprints."
di "========================================"

log close
exit
