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
* firm_productivity_composition.do
* Firm productivity regressions controlling for composition changes
* Following firm_mechanisms.do pattern with composition controls
*============================================================*

clear all
set more off

// Set up central log
capture log close
log using "firm_productivity_composition.log", replace text

// Globals and setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "firm_productivity_composition"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

display "============================================================"
display "Starting Firm Productivity Composition Analysis"
display "============================================================"

*============================================================*
* PART 0: Load base data and prepare growth data
*============================================================*

// Load firm panel
use "$processed_data/firm_panel.dta", clear
display "Loaded firm panel with `=_N' observations"

// Save firm panel as temp file
tempfile firm_data
save `firm_data'

// Prepare role growth data (already in wide format from scaling analysis)
import delimited "$processed_data/role_k7_scaling_growth.csv", clear
gen yh = yh(year, half)
keep companyname yh role_k7 pct_growth_role
reshape wide pct_growth_role, i(companyname yh) j(role_k7) string
rename pct_growth_role* pct_growth_*
tempfile role_growth_wide
save `role_growth_wide'

// Prepare seniority growth data
import delimited "$processed_data/seniority_scaling_growth.csv", clear
gen yh = yh(year, half)
gen sen_label = "sen" + string(seniority_level)
keep companyname yh sen_label pct_growth_seniority
reshape wide pct_growth_seniority, i(companyname yh) j(sen_label) string
rename pct_growth_seniority* pct_growth_*
tempfile seniority_growth_wide
save `seniority_growth_wide'

*============================================================*
* PART A: Role Composition Controls
*============================================================*

display _n "============================================================"
display "PART A: Role Composition Controls"
display "============================================================"

// Reload firm data and merge with role growth
use `firm_data', clear
capture drop _merge  // Drop any existing _merge variable
merge 1:1 companyname yh using `role_growth_wide'
keep if _merge == 1 | _merge == 3  // Keep unmatched firms too
drop _merge

// Define roles
local roles "Admin Engineer Finance Marketing Operations Sales Scientist"

// Set up postfile for role results
capture postclose handle_role
tempfile out_role
postfile handle_role ///
    str20  role ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_role', replace

// First run baseline (no composition controls)
display _n "Running baseline regression (no composition controls)..."
summarize growth_rate_we if covid == 0, meanonly
local pre_mean = r(mean)

// OLS
reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_role ("Baseline") ("OLS") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (`N') (.)
}

// IV
ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_role ("Baseline") ("IV") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
}

// Run regressions for each role
foreach role in `roles' {
    capture confirm variable pct_growth_`role'
    if _rc == 0 {
        display _n "----------------------------------------"
        display "Role: `role'"
        display "----------------------------------------"
        
        // Create interaction variables (following firm_mechanisms pattern)
        gen `role'_growth_covid = covid * pct_growth_`role'
        gen `role'_growth_inter = covid * pct_growth_`role' * remote
        
        // Count non-missing
        count if !missing(pct_growth_`role') & !missing(growth_rate_we)
        local n_comp = r(N)
        display "Observations with composition data: `n_comp'"
        
        // Calculate pre-mean
        summarize growth_rate_we if covid == 0, meanonly
        local pre_mean = r(mean)
        
        // OLS regression
        reghdfe growth_rate_we var3 var5 var4 `role'_growth_covid `role'_growth_inter, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        
        // Store OLS main effects
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_role ("`role'") ("OLS") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        
        // Store OLS interaction effect
        local b    = _b[`role'_growth_inter]
        local se   = _se[`role'_growth_inter]
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_role ("`role'") ("OLS") ("`role'_interaction") ///
                        (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        
        // IV regression
        ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4 `role'_growth_covid `role'_growth_inter, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        local rkf = e(rkf)
        
        // Store IV main effects
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_role ("`role'") ("IV") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
        
        // Store IV interaction effect
        local b    = _b[`role'_growth_inter]
        local se   = _se[`role'_growth_inter]
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_role ("`role'") ("IV") ("`role'_interaction") ///
                        (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        
        // Clean up
        drop `role'_growth_covid `role'_growth_inter
    }
}

// Save role results
postclose handle_role
use `out_role', clear
export delimited using "`result_dir'/role_composition_results.csv", replace
save "`result_dir'/role_composition_results.dta", replace

display _n "Role composition results saved to:"
display "  `result_dir'/role_composition_results.csv"
display "  `result_dir'/role_composition_results.dta"

*============================================================*
* PART B: Seniority Composition Controls
*============================================================*

display _n "============================================================"
display "PART B: Seniority Composition Controls"
display "============================================================"

// Reload firm data and merge with seniority growth
use `firm_data', clear
capture drop _merge  // Drop any existing _merge variable
merge 1:1 companyname yh using `seniority_growth_wide'
keep if _merge == 1 | _merge == 3
drop _merge

// Set up postfile for seniority results
capture postclose handle_sen
tempfile out_sen
postfile handle_sen ///
    str20  seniority ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_sen', replace

// First run baseline (repeated for seniority file)
display _n "Running baseline regression (no composition controls)..."
summarize growth_rate_we if covid == 0, meanonly
local pre_mean = r(mean)

// OLS
reghdfe growth_rate_we var3 var5 var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_sen ("Baseline") ("OLS") ("`p'") ///
                   (`b') (`se') (`pval') (`pre_mean') (`N') (.)
}

// IV
ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id)

local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_sen ("Baseline") ("IV") ("`p'") ///
                   (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
}

// Run regressions for each seniority level
forvalues sen = 1/4 {
    capture confirm variable pct_growth_sen`sen'
    if _rc == 0 {
        display _n "----------------------------------------"
        display "Seniority Level: `sen'"
        display "----------------------------------------"
        
        // Create interaction variables
        gen sen`sen'_growth_covid = covid * pct_growth_sen`sen'
        gen sen`sen'_growth_inter = covid * pct_growth_sen`sen' * remote
        
        // Count non-missing
        count if !missing(pct_growth_sen`sen') & !missing(growth_rate_we)
        local n_comp = r(N)
        display "Observations with composition data: `n_comp'"
        
        // Calculate pre-mean
        summarize growth_rate_we if covid == 0, meanonly
        local pre_mean = r(mean)
        
        // OLS regression
        reghdfe growth_rate_we var3 var5 var4 sen`sen'_growth_covid sen`sen'_growth_inter, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        
        // Store OLS main effects
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_sen ("Level_`sen'") ("OLS") ("`p'") ///
                           (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        
        // Store OLS interaction effect
        local b    = _b[sen`sen'_growth_inter]
        local se   = _se[sen`sen'_growth_inter]
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_sen ("Level_`sen'") ("OLS") ("sen`sen'_interaction") ///
                       (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        
        // IV regression
        ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4 sen`sen'_growth_covid sen`sen'_growth_inter, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        local rkf = e(rkf)
        
        // Store IV main effects
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_sen ("Level_`sen'") ("IV") ("`p'") ///
                           (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
        
        // Store IV interaction effect
        local b    = _b[sen`sen'_growth_inter]
        local se   = _se[sen`sen'_growth_inter]
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_sen ("Level_`sen'") ("IV") ("sen`sen'_interaction") ///
                       (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        
        // Clean up
        drop sen`sen'_growth_covid sen`sen'_growth_inter
    }
}

// Save seniority results
postclose handle_sen
use `out_sen', clear
export delimited using "`result_dir'/seniority_composition_results.csv", replace
save "`result_dir'/seniority_composition_results.dta", replace

display _n "Seniority composition results saved to:"
display "  `result_dir'/seniority_composition_results.csv"
display "  `result_dir'/seniority_composition_results.dta"

*============================================================*
* Summary
*============================================================*

display _n "============================================================"
display "Firm Productivity Composition Analysis Complete"
display "============================================================"
display "Results saved in: `result_dir'/"
display "  - role_composition_results.csv/.dta"
display "  - seniority_composition_results.csv/.dta"
display "Central log: firm_productivity_composition.log"

log close