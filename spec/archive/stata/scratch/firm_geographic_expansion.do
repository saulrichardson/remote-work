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
*  firm_geographic_expansion.do
*  — Test whether remote work enables geographic expansion
*    Uses the new geographic expansion metrics from Python
*============================================================*

// 0) Setup environment
do "../globals.do"

// Setup logging
local specname "firm_geographic_expansion"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


// 1) Load firm panel with standard variables
use "$processed_data/firm_panel.dta", clear

// 2) Merge geographic expansion metrics
preserve
    import delimited "$processed_data/firm_geographic_expansion.csv", clear
    
    // Standardize firm name to match panel
    gen companyname_lower = lower(firm)
    drop firm
    rename companyname_lower companyname
    
    // Keep only the key variables we need
    keep companyname yh share_new_geo new_geo_hires total_hires n_new_locations
    
    // Create additional metrics
    gen has_new_geo = (n_new_locations > 0)
    gen log_new_locations = log(n_new_locations + 1)
    
    tempfile geo_expansion
    save `geo_expansion'
restore

// Merge with main panel
merge 1:1 companyname yh using `geo_expansion', keep(1 3)
gen has_geo_data = (_merge == 3)
drop _merge

// 3) Fill missing values for firms with no hires
* If a firm had no hires in a period, they have 0 new geography expansion
replace share_new_geo = 0 if missing(share_new_geo) & has_geo_data == 0
replace n_new_locations = 0 if missing(n_new_locations) & has_geo_data == 0
replace has_new_geo = 0 if missing(has_new_geo) & has_geo_data == 0

// 4) Create winsorized version for robustness
* Winsorize at 1% and 99% to handle outliers
winsor2 share_new_geo, cuts(1 99) suffix(_w)
winsor2 n_new_locations, cuts(1 99) suffix(_w)

// 5) Summary statistics
di _n "=== Summary Statistics for Geographic Expansion ===" _n

* Pre-period (2019)
qui sum share_new_geo if covid == 0
di "Pre-COVID share in new geography: " %4.1f r(mean)*100 "%"

* Post-period (2020+)
qui sum share_new_geo if covid == 1
di "Post-COVID share in new geography: " %4.1f r(mean)*100 "%"

* By remote status
table remote covid, contents(mean share_new_geo) format(%9.3f)

// 6) Prepare output
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

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

// 7) Main regressions for geographic expansion outcomes
local outcomes share_new_geo share_new_geo_w n_new_locations n_new_locations_w has_new_geo

foreach y of local outcomes {
    di _n "→ Processing outcome: `y'"
    
    // Check if we have enough variation
    qui sum `y' if !missing(var3, var5, var4)
    if r(sd) == 0 {
        di "  Skipping `y' - no variation"
        continue
    }
    
    // Pre-period mean
    qui sum `y' if covid == 0
    local pre_mean = r(mean)
    di "  Pre-period mean: " %6.3f `pre_mean'
    
    // --- OLS ---
    qui reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)
    
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }
    
    // --- IV (2nd stage) ---
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
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
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

// 8) Export results to CSV
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", replace

// 9) Additional analysis: Heterogeneity by firm characteristics

use "$processed_data/firm_panel.dta", clear
merge 1:1 companyname yh using `geo_expansion', keep(1 3) nogen

// Create startup indicator (founded after 2010)
gen startup = (founding_year >= 2010) if !missing(founding_year)

// Interaction regressions
di _n "=== Heterogeneity Analysis by Startup Status ===" _n

* Main effect for all firms
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)
est store main

* Separate for startups
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4 if startup == 1, ///
    absorb(firm_id yh) vce(cluster firm_id)
est store startup_yes

* Separate for established firms
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4 if startup == 0, ///
    absorb(firm_id yh) vce(cluster firm_id)
est store startup_no

// Display comparison
esttab main startup_yes startup_no, ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var4) ///
    mtitles("All Firms" "Startups" "Established") ///
    stats(N rkf, fmt(0 2) labels("Observations" "KP rk F-stat"))

// 10) Create summary table for meeting
di _n "=== Summary for Meeting ===" _n
di "Key Finding: Remote work × Post-COVID effect on geographic expansion"
di "─────────────────────────────────────────────────────────────"

qui: ivreghdfe share_new_geo (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

di "Share of hires in new geographies:"
di "  Coefficient (var3): " %6.3f _b[var3]
di "  Standard error: " %6.3f _se[var3]
di "  P-value: " %6.4f 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))

local effect_size = _b[var3] * 100
di _n "Interpretation: Remote firms hire " %4.1f abs(`effect_size') "pp " ///
    cond(`effect_size' > 0, "more", "fewer") " in new geographies post-COVID"

log close

di _n "Results saved to: `result_dir'/consolidated_results.csv"
