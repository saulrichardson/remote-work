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
==============================================================================
THREE-WAY SUBSTITUTION ANALYSIS (clean spec using firm-entry hires)
==============================================================================
Inputs: data/processed/firm_panel_threeway_geography.csv
Sample: Post-period (covid==1) firm-periods with actual hiring (no_hire==0)
Outcomes: share_new_msa, share_remote, total_dispersion, share_legacy_msa
Endogenous: var3 var5   |  Instruments: var6 var7
Fixed effects: firm_id yh_int   |  SEs: clustered by firm_id
==============================================================================
*/

clear all
set more off

capture which ivreghdfe
if _rc {
    di as error "ivreghdfe not installed. Run: ssc install ivreghdfe, replace"
}

// Load merged panel
import delimited "data/processed/firm_panel_threeway_geography.csv", clear varnames(1)

// Firm ID
capture confirm variable firm_id
if _rc {
    encode companyname, gen(firm_id)
}

// Ensure yh_int exists
capture confirm variable yh_int
if _rc {
    // If yh is present as numeric half-year, coerce; if datetime, compute
    capture confirm variable yh
    if !_rc {
        gen long yh_int = .
        capture confirm numeric variable yh
        if !_rc {
            replace yh_int = yh if yh<. // assume already half-year index
        }
        else {
            // If yh is string/datetime, attempt parse year-half
            // Fallback: drop if missing after parse
            // (Most pipelines already carry yh_int.)
            di as txt "Note: yh_int not found; attempting to use yh as-is."
        }
    }
}

// No explicit subsetting: rely on Stata to drop missings per outcome
di _n "=========================================="
di "SAMPLE (NO EXPLICIT FILTERS)"
di "=========================================="
di "N (firm-periods) = " _N

// Quick summary (all rows)
tabstat share_legacy_msa share_new_msa share_remote total_dispersion, ///
    stat(mean sd p50 min max n) columns(statistics) format(%9.4f)

// =============================
// Main IV regressions
// =============================

tempname res
matrix `res' = J(4, 5, .)
matrix rownames `res' = "New_MSA" "Remote" "Total_Dispersion" "Legacy_MSA"
matrix colnames `res' = "Coef_var3" "SE" "P" "CI_L" "CI_H"

// 1) New MSA — IV
ivreghdfe share_new_msa (var3 var5 = var6 var7) var4, absorb(firm_id yh_int) ///
    vce(cluster firm_id)
matrix `res'[1,1] = _b[var3]
matrix `res'[1,2] = _se[var3]
matrix `res'[1,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res'[1,4] = _b[var3] - 1.96*_se[var3]
matrix `res'[1,5] = _b[var3] + 1.96*_se[var3]
scalar kp_new = e(rkf)

// 2) Remote — IV
ivreghdfe share_remote (var3 var5 = var6 var7) var4, absorb(firm_id yh_int) ///
    vce(cluster firm_id)
matrix `res'[2,1] = _b[var3]
matrix `res'[2,2] = _se[var3]
matrix `res'[2,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res'[2,4] = _b[var3] - 1.96*_se[var3]
matrix `res'[2,5] = _b[var3] + 1.96*_se[var3]
scalar kp_rem = e(rkf)

// 3) Total dispersion (identity: new + remote) — IV
ivreghdfe total_dispersion (var3 var5 = var6 var7) var4, absorb(firm_id yh_int) ///
    vce(cluster firm_id)
matrix `res'[3,1] = _b[var3]
matrix `res'[3,2] = _se[var3]
matrix `res'[3,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res'[3,4] = _b[var3] - 1.96*_se[var3]
matrix `res'[3,5] = _b[var3] + 1.96*_se[var3]
scalar kp_disp = e(rkf)

// 4) Legacy MSA — IV
ivreghdfe share_legacy_msa (var3 var5 = var6 var7) var4, absorb(firm_id yh_int) ///
    vce(cluster firm_id)
matrix `res'[4,1] = _b[var3]
matrix `res'[4,2] = _se[var3]
matrix `res'[4,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res'[4,4] = _b[var3] - 1.96*_se[var3]
matrix `res'[4,5] = _b[var3] + 1.96*_se[var3]
scalar kp_leg = e(rkf)

di _n _dup(70) "="
di "MAIN RESULTS (var3 coefficient)"
di _dup(70) "="
matlist `res', format(%9.4f) lines(oneline)

// Diagnostics
// (First-stage diagnostics suppressed in v2)

// Identities check
scalar b_new = `res'[1,1]
scalar b_rem = `res'[2,1]
scalar b_dis = `res'[3,1]
scalar b_leg = `res'[4,1]
di _n "Identity checks:"
di "  new + remote vs total_dispersion : " %7.4f (b_new + b_rem) " vs " %7.4f b_dis
di "  legacy + new + remote (should ~0) : " %7.4f (b_leg + b_new + b_rem)

// =============================
// Parallel OLS regressions
// =============================

di _n _dup(70) "="
di "OLS RESULTS (var3 coefficient)"
di _dup(70) "="

tempname res_ols
matrix `res_ols' = J(4, 5, .)
matrix rownames `res_ols' = "New_MSA" "Remote" "Total_Dispersion" "Legacy_MSA"
matrix colnames `res_ols' = "Coef_var3" "SE" "P" "CI_L" "CI_H"

reghdfe share_new_msa var3 var5 var4, absorb(firm_id yh_int) vce(cluster firm_id)
matrix `res_ols'[1,1] = _b[var3]
matrix `res_ols'[1,2] = _se[var3]
matrix `res_ols'[1,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res_ols'[1,4] = _b[var3] - 1.96*_se[var3]
matrix `res_ols'[1,5] = _b[var3] + 1.96*_se[var3]

reghdfe share_remote var3 var5 var4, absorb(firm_id yh_int) vce(cluster firm_id)
matrix `res_ols'[2,1] = _b[var3]
matrix `res_ols'[2,2] = _se[var3]
matrix `res_ols'[2,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res_ols'[2,4] = _b[var3] - 1.96*_se[var3]
matrix `res_ols'[2,5] = _b[var3] + 1.96*_se[var3]

reghdfe total_dispersion var3 var5 var4, absorb(firm_id yh_int) vce(cluster firm_id)
matrix `res_ols'[3,1] = _b[var3]
matrix `res_ols'[3,2] = _se[var3]
matrix `res_ols'[3,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res_ols'[3,4] = _b[var3] - 1.96*_se[var3]
matrix `res_ols'[3,5] = _b[var3] + 1.96*_se[var3]

reghdfe share_legacy_msa var3 var5 var4, absorb(firm_id yh_int) vce(cluster firm_id)
matrix `res_ols'[4,1] = _b[var3]
matrix `res_ols'[4,2] = _se[var3]
matrix `res_ols'[4,3] = 2*ttail(e(df_r), abs(_b[var3]/_se[var3]))
matrix `res_ols'[4,4] = _b[var3] - 1.96*_se[var3]
matrix `res_ols'[4,5] = _b[var3] + 1.96*_se[var3]

matlist `res_ols', format(%9.4f) lines(oneline) ///
    title("OLS: Treatment Effect on Hiring Shares (var3 coefficient)")

di _n _dup(70) "="
di "ANALYSIS COMPLETE (v2)"
di _dup(70) "="

// =============================
// Save IV + OLS results to CSV
// =============================

cap mkdir "results"

tempfile out_iv out_ols
capture postclose handle_iv
postfile handle_iv str8 model str20 outcome double coef se p ci_l ci_h using `out_iv', replace

local outcomes "New_MSA Remote Total_Dispersion Legacy_MSA"
local i = 1
foreach nm of local outcomes {
    post handle_iv ("IV") ("`nm'") (`res'[`i',1]) (`res'[`i',2]) (`res'[`i',3]) (`res'[`i',4]) (`res'[`i',5])
    local ++i
}
postclose handle_iv

capture postclose handle_ols
postfile handle_ols str8 model str20 outcome double coef se p ci_l ci_h using `out_ols', replace
local i = 1
foreach nm of local outcomes {
    post handle_ols ("OLS") ("`nm'") (`res_ols'[`i',1]) (`res_ols'[`i',2]) (`res_ols'[`i',3]) (`res_ols'[`i',4]) (`res_ols'[`i',5])
    local ++i
}
postclose handle_ols

preserve
use `out_iv', clear
append using `out_ols'
export delimited using "results/threeway_v2_results.csv", replace
restore

// =============================
// Per-outcome tables (IV + OLS; var3, var4, var5)
// =============================

cap mkdir "results/raw"
// Core outcomes for this analysis
local outcomes "share_new_msa share_remote total_dispersion share_legacy_msa"
foreach y of local outcomes {
    capture confirm variable `y'
    if _rc continue
    tempname outmat
    tempfile outcsv
    capture postclose H
    // Add N, mean (dep var), and KP rk Wald F (IV only)
    postfile H str8 model double coef_v3 se_v3 p_v3 coef_v4 se_v4 p_v4 coef_v5 se_v5 p_v5 ///
        double N depmean kpf using `outcsv', replace

    // IV
    ivreghdfe `y' (var3 var5 = var6 var7) var4, absorb(firm_id yh_int) vce(cluster firm_id)
    qui summ `y' if e(sample), meanonly
    local ybar = r(mean)
    post H ("IV") (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var4]) (_se[var4]) (2*ttail(e(df_r), abs(_b[var4]/_se[var4])))     ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5])))     ///
            (e(N)) (`ybar') (e(rkf))

    // OLS
    reghdfe `y' var3 var5 var4, absorb(firm_id yh_int) vce(cluster firm_id)
    qui summ `y' if e(sample), meanonly
    local ybar = r(mean)
    post H ("OLS") (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
            (_b[var4]) (_se[var4]) (2*ttail(e(df_r), abs(_b[var4]/_se[var4])))     ///
            (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5])))     ///
            (e(N)) (`ybar') (.)

    postclose H
    preserve
    use `outcsv', clear
    export delimited using "results/raw/threeway_v2_`y'.csv", replace
    restore
}

exit
