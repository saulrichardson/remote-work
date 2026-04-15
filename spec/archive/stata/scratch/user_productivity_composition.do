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
* user_productivity_composition.do
* User productivity regressions controlling for firm composition changes
* Following user_mechanisms_lean.do pattern
*============================================================*

clear all
set more off

// Set up central log
capture log close
log using "user_productivity_composition.log", replace text

// Globals and setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "user_productivity_composition"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

display "============================================================"
display "Starting User Productivity Composition Analysis"
display "============================================================"

*============================================================*
* PART 0: Load base data and prepare growth data
*============================================================*

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear
display "Loaded user panel with `=_N' observations"

// Save user panel as temp file
tempfile user_data
save `user_data'

// Prepare role growth and share data (already in long format)
import delimited "$processed_data/role_k7_scaling_growth.csv", clear
gen yh = yh(year, half)

// Growth wide
preserve
    keep companyname yh role_k7 pct_growth_role
    reshape wide pct_growth_role, i(companyname yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    tempfile role_growth_wide
    save `role_growth_wide'
restore

// Share wide
keep companyname yh role_k7 role_share
reshape wide role_share, i(companyname yh) j(role_k7) string
rename role_share* share_*
tempfile role_share_wide
save `role_share_wide'

// Prepare seniority growth and share data
import delimited "$processed_data/seniority_scaling_growth.csv", clear
gen yh = yh(year, half)
gen sen_label = "sen" + string(seniority_level)

// Growth wide
preserve
    keep companyname yh sen_label pct_growth_seniority
    reshape wide pct_growth_seniority, i(companyname yh) j(sen_label) string
    rename pct_growth_seniority* pct_growth_*
    tempfile seniority_growth_wide
    save `seniority_growth_wide'
restore

// Share wide
keep companyname yh sen_label seniority_share
reshape wide seniority_share, i(companyname yh) j(sen_label) string
rename seniority_share* share_*
tempfile seniority_share_wide
save `seniority_share_wide'

*============================================================*
* PART A: Role Composition Controls
*============================================================*

display _n "============================================================"
display "PART A: Role Composition Controls"
display "============================================================"

// Reload user data and merge with role growth
use `user_data', clear
capture drop _merge  // Drop any existing _merge variable
merge m:1 companyname yh using `role_growth_wide'
keep if _merge == 1 | _merge == 3  // Keep unmatched users too
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
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// OLS
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons

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
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons

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
        
        // Create interaction variables (following user_mechanisms pattern)
        gen `role'_growth_covid = covid * pct_growth_`role'
        gen `role'_growth_inter = covid * pct_growth_`role' * startup
        
        // Count non-missing
        count if !missing(pct_growth_`role') & !missing(total_contributions_q100)
        local n_comp = r(N)
        display "Observations with composition data: `n_comp'"
        
        // Calculate pre-mean
        summarize total_contributions_q100 if covid == 0, meanonly
        local pre_mean = r(mean)
        
        // OLS regression
        reghdfe total_contributions_q100 var3 var5 var4 `role'_growth_covid `role'_growth_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        
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
        ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 `role'_growth_covid `role'_growth_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        
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
* PART A2: Role Composition Controls (Shares)
*============================================================*

// Reload user data and merge with role shares
use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `role_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

// Fill missing role shares with 0 when any share is present for the firm×half-year
// This prevents listwise deletion from spurious missings created by growth-file filters
capture unab sharevars: share_*
if _rc == 0 {
    // Unconditionally set missing shares to 0 to retain rows in regressions
    foreach v of local sharevars {
        quietly replace `v' = 0 if missing(`v')
    }
}

// Set up postfile for role share results
capture postclose handle_role_sh
tempfile out_role_sh
postfile handle_role_sh ///
    str20  role ///
    str8   model_type ///
    str40  param ///
    double coef se pval pre_mean nobs rkf ///
    using `out_role_sh', replace

local roles "Admin Engineer Finance Marketing Operations Sales Scientist"
// Baseline (no composition controls)
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)
reghdfe total_contributions_q100 var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_role_sh ("Baseline") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
}
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_role_sh ("Baseline") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
}

foreach role in `roles' {
    capture confirm variable share_`role'
    if _rc == 0 {
        gen `role'_share_covid = covid * share_`role'
        gen `role'_share_inter = covid * share_`role' * startup

        count if !missing(share_`role') & !missing(total_contributions_q100)
        summarize total_contributions_q100 if covid == 0, meanonly
        local pre_mean = r(mean)

        // OLS
        reghdfe total_contributions_q100 var3 var5 var4 `role'_share_covid `role'_share_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        local N = e(N)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_role_sh ("`role'") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        // Interaction effect
        local b = _b[`role'_share_inter]
        local se = _se[`role'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_role_sh ("`role'") ("OLS") ("`role'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (.)

        // IV
        ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 `role'_share_covid `role'_share_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        local N = e(N)
        local rkf = e(rkf)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_role_sh ("`role'") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
        local b = _b[`role'_share_inter]
        local se = _se[`role'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_role_sh ("`role'") ("IV") ("`role'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')

        drop `role'_share_covid `role'_share_inter
    }
}

postclose handle_role_sh
use `out_role_sh', clear
export delimited using "`result_dir'/role_composition_share_results.csv", replace
save "`result_dir'/role_composition_share_results.dta", replace

*============================================================*
* PART B: Seniority Composition Controls
*============================================================*

display _n "============================================================"
display "PART B: Seniority Composition Controls"
display "============================================================"

// Reload user data and merge with seniority growth
use `user_data', clear
capture drop _merge  // Drop any existing _merge variable
merge m:1 companyname yh using `seniority_growth_wide'
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
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// OLS
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons

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
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons

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
        gen sen`sen'_growth_inter = covid * pct_growth_sen`sen' * startup
        
        // Count non-missing
        count if !missing(pct_growth_sen`sen') & !missing(total_contributions_q100)
        local n_comp = r(N)
        display "Observations with composition data: `n_comp'"
        
        // Calculate pre-mean
        summarize total_contributions_q100 if covid == 0, meanonly
        local pre_mean = r(mean)
        
        // OLS regression
        reghdfe total_contributions_q100 var3 var5 var4 sen`sen'_growth_covid sen`sen'_growth_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        
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
        ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 sen`sen'_growth_covid sen`sen'_growth_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        
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
* PART B2: Seniority Composition Controls (Shares)
*============================================================*

// Reload user data and merge with seniority shares
use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `seniority_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

// Fill missing seniority shares with 0 when any share is present for the firm×half-year
capture unab svars: share_sen*
if _rc == 0 {
    // Unconditionally set missing seniority shares to 0
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

// Baseline (no composition controls)
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)
reghdfe total_contributions_q100 var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_sen_sh ("Baseline") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
}
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_sen_sh ("Baseline") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
}

forvalues sen = 1/4 {
    capture confirm variable share_sen`sen'
    if _rc == 0 {
        gen sen`sen'_share_covid = covid * share_sen`sen'
        gen sen`sen'_share_inter = covid * share_sen`sen' * startup

        count if !missing(share_sen`sen') & !missing(total_contributions_q100)
        summarize total_contributions_q100 if covid == 0, meanonly
        local pre_mean = r(mean)

        // OLS
        reghdfe total_contributions_q100 var3 var5 var4 sen`sen'_share_covid sen`sen'_share_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id)
        local N = e(N)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_sen_sh ("Level_`sen'") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        local b = _b[sen`sen'_share_inter]
        local se = _se[sen`sen'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_sen_sh ("Level_`sen'") ("OLS") ("sen`sen'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (.)

        // IV
        ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 sen`sen'_share_covid sen`sen'_share_inter, ///
            absorb(firm_id#user_id yh) vce(cluster user_id)
        local N = e(N)
        local rkf = e(rkf)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_sen_sh ("Level_`sen'") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
        local b = _b[sen`sen'_share_inter]
        local se = _se[sen`sen'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_sen_sh ("Level_`sen'") ("IV") ("sen`sen'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')

        drop sen`sen'_share_covid sen`sen'_share_inter
    }
}

postclose handle_sen_sh
use `out_sen_sh', clear
export delimited using "`result_dir'/seniority_composition_share_results.csv", replace
save "`result_dir'/seniority_composition_share_results.dta", replace

*============================================================*
* Summary
*============================================================*

display _n "============================================================"
display "User Productivity Composition Analysis Complete"
display "============================================================"
display "Results saved in: `result_dir'/"
display "  - role_composition_results.csv/.dta"
display "  - seniority_composition_results.csv/.dta"
display "  - role_composition_share_results.csv/.dta"
display "  - seniority_composition_share_results.csv/.dta"
display "Central log: user_productivity_composition.log"

log close
