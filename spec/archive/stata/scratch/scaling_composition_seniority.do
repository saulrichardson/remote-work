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
* scaling_composition_seniority.do
* Seniority-specific scaling regressions
*============================================================*

clear all
set more off

// Set up log
capture log close
log using "scaling_composition_seniority.log", replace text

// Globals and setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "scaling_composition_seniority"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

display "============================================================"
display "Starting Scaling Composition Seniority Analysis"
display "============================================================"

// Load seniority growth/share data first
import delimited "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/seniority_scaling_growth.csv", clear

// Create yh variable using Stata's yh() function
gen yh = yh(year, half)

// Create seniority label for reshape
gen sen_label = "sen" + string(seniority_level)

// Growth reshape
preserve
    keep companyname yh sen_label pct_growth_seniority
    rename pct_growth_seniority pct_growth_
    reshape wide pct_growth_, i(companyname yh) j(sen_label) string
    tempfile seniority_growth
    save `seniority_growth'
restore

// Share reshape
keep companyname yh sen_label seniority_share
rename seniority_share share_
reshape wide share_, i(companyname yh) j(sen_label) string
tempfile seniority_share_wide
save `seniority_share_wide'

// Load firm panel
use "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/firm_panel.dta", clear

// Merge with seniority growth data (now 1:1 merge at firm-yh level)
merge 1:1 companyname yh using `seniority_growth'
keep if _merge == 3
drop _merge

// Set up postfile for results
capture postclose handle_sen
tempfile out_sen
postfile handle_sen ///
    str20  seniority ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_sen', replace



// Run regression for each seniority level
forvalues sen = 1/4 {
    di _n "========================================"
    di "Seniority Level: `sen'"
    di "========================================"
    
    // Count non-missing observations
    count if !missing(pct_growth_sen`sen')
    di "Non-missing observations: " r(N)
    
    // Calculate pre-COVID mean
    sum pct_growth_sen`sen' if covid == 0
    local pre_mean = r(mean)
    di "Pre-COVID mean: " `pre_mean'
    
    // OLS regression
    reghdfe pct_growth_sen`sen' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    
    local N = e(N)
    
    // Store OLS results
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_sen ("Level_`sen'") ("OLS") ("`p'") ///
                       (`b') (`se') (`pval') (`pre_mean') (`N') (.)
    }
    
    // IV regression
    ivreghdfe pct_growth_sen`sen' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id)
    
    local N = e(N)
    local rkf = e(rkf)
    
    // Store IV results
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_sen ("Level_`sen'") ("IV") ("`p'") ///
                       (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
    }
}

// Save results
postclose handle_sen
use `out_sen', clear
export delimited using "`result_dir'/seniority_scaling_results.csv", replace
save "`result_dir'/seniority_scaling_results.dta", replace

display _n "============================================================"
display "Scaling Composition Seniority Analysis Complete"
display "============================================================"
display "Results saved in: `result_dir'/"
display "  - seniority_scaling_results.csv"
display "  - seniority_scaling_results.dta"
display "Central log: scaling_composition_seniority.log"

log close

// =====================
// Share-based outcomes
// =====================

// Merge share data to firm panel and run regressions on share outcomes
use "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/firm_panel.dta", clear
merge 1:1 companyname yh using `seniority_share_wide'
keep if _merge == 3
drop _merge

// FIXED zero-fill logic for seniority
capture unab svars: share_sen*
if _rc == 0 {
    foreach v of local svars {
        quietly replace `v' = 0 if missing(`v')
    }
}

capture postclose handle_sen_sh
tempfile out_sen_sh
postfile handle_sen_sh ///
    str20  seniority ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_sen_sh', replace

forvalues sen = 1/4 {
    capture confirm variable share_sen`sen'
    if _rc == 0 {
        di _n "Share outcome — Seniority Level: `sen'"
        count if !missing(share_sen`sen')
        sum share_sen`sen' if covid == 0
        local pre_mean = r(mean)

        // OLS
        reghdfe share_sen`sen' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        local N = e(N)
        foreach p in var3 var5 var4 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_sen_sh ("Level_`sen'") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }

        // IV
        ivreghdfe share_sen`sen' (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
        local N = e(N)
        local rkf = e(rkf)
        foreach p in var3 var5 var4 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_sen_sh ("Level_`sen'") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
    }
}

postclose handle_sen_sh
use `out_sen_sh', clear
export delimited using "`result_dir'/seniority_scaling_share_results.csv", replace
save "`result_dir'/seniority_scaling_share_results.dta", replace
