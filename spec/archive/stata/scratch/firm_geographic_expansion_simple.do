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
*  firm_geographic_expansion_simple.do
*  — Run IV regression on geographic expansion outcome
*    Uses pre-merged data from Python
*============================================================*

// 0) Setup environment
do "../globals.do"

// Setup logging
local specname "firm_geographic_expansion_simple"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


// 1) Load the pre-merged data from Python
import delimited "$processed_data/firm_panel_with_geo_analysis.csv", clear

di _n "=== Data Loaded ===" _n
di "Observations: " _N
sum share_new_geo var3 var5 var4 var6 var7, detail

// 2) Check that we have the necessary variables
foreach v in share_new_geo var3 var5 var4 var6 var7 firm_id {
    capture confirm variable `v'
    if _rc {
        di "ERROR: Variable `v' not found"
        exit 1
    }
}

// 3) Create numeric firm_id if needed
capture confirm numeric variable firm_id
if _rc {
    encode companyname, gen(firm_id_num)
    drop firm_id
    rename firm_id_num firm_id
}

// Create numeric yh if needed (using yh_int from Python)
capture confirm variable yh_int
if !_rc {
    rename yh_int yh_numeric
}
else {
    gen yh_numeric = yh
}

// 4) Summary statistics
di _n "=== Summary Statistics ===" _n
sum share_new_geo if !missing(var3, var5, var4)
local mean_share = r(mean)
di "Mean share in new geography: " %6.3f `mean_share'

// By treatment status
di _n "By var3 (remote × covid):"
tabstat share_new_geo, by(var3) stats(mean sd n)

// 5) Run main regressions
di _n "=== MAIN REGRESSIONS ===" _n

// --- OLS ---
di _n "OLS REGRESSION:"
di "---------------"
reghdfe share_new_geo var3 var5 var4, ///
    absorb(firm_id yh_numeric) vce(cluster firm_id)
    
est store ols_geo

// Store OLS results
local b_ols_var3 = _b[var3]
local se_ols_var3 = _se[var3]
local p_ols_var3 = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))

// --- IV ---
di _n "IV REGRESSION:"
di "--------------"
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh_numeric) vce(cluster firm_id) first

est store iv_geo

// Store IV results
local b_iv_var3 = _b[var3]
local se_iv_var3 = _se[var3]
local p_iv_var3 = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
local rkf = e(rkf)

// 6) Display results summary
di _n "==========================================="
di "SUMMARY OF RESULTS"
di "==========================================="
di _n "Outcome: Share of hires in new geography (0-1 scale)"
di "Treatment: var3 (remote × covid)"
di _n "OLS Results:"
di "  Coefficient: " %7.4f `b_ols_var3'
di "  Std Error: " %7.4f `se_ols_var3'
di "  P-value: " %6.4f `p_ols_var3'

di _n "IV Results:"
di "  Coefficient: " %7.4f `b_iv_var3'
di "  Std Error: " %7.4f `se_iv_var3'  
di "  P-value: " %6.4f `p_iv_var3'
di "  KP F-stat: " %6.2f `rkf'

// Interpretation
if `p_iv_var3' < 0.10 {
    local effect = `b_iv_var3' * 100
    di _n "INTERPRETATION:"
    if `b_iv_var3' > 0 {
        di "Remote firms have " %4.1f abs(`effect') " percentage points MORE"
        di "hires in new (non-2019) geographies post-COVID."
    }
    else {
        di "Remote firms have " %4.1f abs(`effect') " percentage points FEWER"
        di "hires in new (non-2019) geographies post-COVID."
    }
}
else {
    di _n "No statistically significant effect at 10% level."
}

// 7) Robustness checks
di _n "=== ROBUSTNESS CHECKS ===" _n

// Intensive margin only (firms with positive hiring)
di "Intensive margin (exclude zero-hire periods):"
ivreghdfe share_new_geo (var3 var5 = var6 var7) var4 if total_hires > 0, ///
    absorb(firm_id yh_numeric) vce(cluster firm_id)

// Extensive margin
gen has_new_geo = (n_new_locations > 0) if !missing(n_new_locations)
di _n "Extensive margin (any new geography):"
ivreghdfe has_new_geo (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh_numeric) vce(cluster firm_id)

// 8) Output table
esttab ols_geo iv_geo, ///
    b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var4) ///
    mtitles("OLS" "IV") ///
    stats(N r2 rkf, fmt(0 3 2) labels("N" "R-sq" "KP F-stat")) ///
    title("Geographic Expansion Results") ///
    nonotes

log close
