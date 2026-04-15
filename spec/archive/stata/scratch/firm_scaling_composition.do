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
*  firm_scaling_composition.do
*  — Scaling regressions by role and seniority level
*  — Uses same RHS spec as firm_scaling.do but with role/seniority growth as outcomes
*============================================================*

// 0) Setup environment
quietly {
    // Set up paths manually to avoid globals.do issues
    global src "/Users/saul/Dropbox/Remote Work Startups/main/src"
    global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
    global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"
}

// 1) Prepare output directories and logs
local specname   "firm_scaling_composition"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 2) Load firm panel data
use "$processed_data/firm_panel.dta", clear

// Keep variables we need
keep firm_id companyname yh year half covid remote teleworkable ///
     var3 var4 var5 var6 var7  // Keep the interaction variables

// Save a temp version for merging
tempfile firm_data
save `firm_data'

*============================================================*
* PART A: Role-based scaling regressions
*============================================================*

// 3) Load role growth data and reshape to wide
import delimited "$processed_data/role_k7_scaling_growth.csv", clear

// Clean role names (remove any special characters/spaces)
replace role_k7 = subinstr(role_k7, " ", "", .)
replace role_k7 = subinstr(role_k7, `"""', "", .)

// Keep only valid roles
keep if inlist(role_k7, "Admin", "Engineer", "Finance", "Marketing", "Operations", "Sales", "Scientist")

// Create year-half variable to match firm panel
gen yh = year * 10 + half

// Rename growth variable for reshape
rename pct_growth_role growth_

// Keep relevant variables and reshape
keep companyname role_k7 yh growth_
reshape wide growth_, i(companyname yh) j(role_k7) string

// Merge with firm panel data
merge 1:1 companyname yh using `firm_data'
keep if _merge == 3  // Keep only matched observations
drop _merge

// Define role list
local roles "Admin Engineer Finance Marketing Operations Sales Scientist"

// Create postfile for results
capture postclose handle_role
tempfile out_role
postfile handle_role ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out_role', replace

// 4) Run regressions for each role
foreach role of local roles {
    
    // Check if variable exists
    capture confirm variable growth_`role'
    if _rc == 0 {
        
        di as text _n "→ Processing growth_`role'"
        
        // Calculate pre-COVID mean
        summarize growth_`role' if covid == 0, meanonly
        local pre_mean = r(mean)
        
        // OLS regression
        reghdfe growth_`role' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        
        // Store results for var3 (covid*remote) and var5 (covid*teleworkable)
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_role ("OLS") ("growth_`role'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (.) (`N')
        }
        
        // IV regression
        ivreghdfe growth_`role' (var3 var5 = var6 var7) var4, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local rkf = e(rkf)
        local N = e(N)
        
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_role ("IV") ("growth_`role'") ("`p'") ///
                            (`b') (`se') (`pval') (`pre_mean') ///
                            (`rkf') (`N')
        }
    }
}

// Close and save role results
postclose handle_role
use `out_role', clear
export delimited using "`result_dir'/role_scaling_results.csv", replace

di as result _n "→ Role scaling results saved to: `result_dir'/role_scaling_results.csv"

*============================================================*
* PART B: Seniority-based scaling regressions
*============================================================*

// 5) Load seniority growth data and reshape
use `firm_data', clear  // Start fresh with firm data

import delimited "$processed_data/seniority_scaling_growth.csv", clear

// Create year-half variable
gen yh = year * 10 + half

// Create seniority label for reshape
gen seniority_label = "sen" + string(seniority_level)

// Rename for reshape
rename pct_growth_seniority growth_

// Keep relevant variables and reshape
keep companyname seniority_label yh growth_
reshape wide growth_, i(companyname yh) j(seniority_label) string

// Merge with firm panel data
merge 1:1 companyname yh using `firm_data'
keep if _merge == 3
drop _merge

// Define seniority levels
local seniority_levels "sen1 sen2 sen3 sen4"

// Create postfile for seniority results
capture postclose handle_sen
tempfile out_sen
postfile handle_sen ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out_sen', replace

// 6) Run regressions for each seniority level
foreach sen of local seniority_levels {
    
    capture confirm variable growth_`sen'
    if _rc == 0 {
        
        di as text _n "→ Processing growth_`sen'"
        
        // Calculate pre-COVID mean
        summarize growth_`sen' if covid == 0, meanonly
        local pre_mean = r(mean)
        
        // OLS regression
        reghdfe growth_`sen' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        
        local N = e(N)
        
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_sen ("OLS") ("growth_`sen'") ("`p'") ///
                           (`b') (`se') (`pval') (`pre_mean') ///
                           (.) (`N')
        }
        
        // IV regression
        ivreghdfe growth_`sen' (var3 var5 = var6 var7) var4, ///
            absorb(firm_id yh) vce(cluster firm_id)
        
        local rkf = e(rkf)
        local N = e(N)
        
        foreach p in var3 var5 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_sen ("IV") ("growth_`sen'") ("`p'") ///
                           (`b') (`se') (`pval') (`pre_mean') ///
                           (`rkf') (`N')
        }
    }
}

// Close and save seniority results
postclose handle_sen
use `out_sen', clear
export delimited using "`result_dir'/seniority_scaling_results.csv", replace

di as result "→ Seniority scaling results saved to: `result_dir'/seniority_scaling_results.csv"

*============================================================*
* PART C: Create summary table combining all results
*============================================================*

// 7) Combine role and seniority results
import delimited "`result_dir'/role_scaling_results.csv", clear
gen category = "role"
tempfile roles_data
save `roles_data'

import delimited "`result_dir'/seniority_scaling_results.csv", clear  
gen category = "seniority"

append using `roles_data'

// Keep only covid*remote effects (var3) for main table
keep if param == "var3"

// Create clean outcome labels
gen outcome_clean = substr(outcome, 8, .)  // Remove "growth_" prefix

// Sort for presentation
gen sort_order = .
replace sort_order = 1 if outcome_clean == "Engineer"
replace sort_order = 2 if outcome_clean == "Sales"
replace sort_order = 3 if outcome_clean == "Admin"
replace sort_order = 4 if outcome_clean == "Operations"
replace sort_order = 5 if outcome_clean == "Marketing"
replace sort_order = 6 if outcome_clean == "Finance"
replace sort_order = 7 if outcome_clean == "Scientist"
replace sort_order = 8 if outcome_clean == "sen1"
replace sort_order = 9 if outcome_clean == "sen2"
replace sort_order = 10 if outcome_clean == "sen3"
replace sort_order = 11 if outcome_clean == "sen4"

sort model_type sort_order

// Export summary table
export delimited using "`result_dir'/composition_scaling_summary.csv", replace

di as result _n "============================================================"
di as result "All composition scaling results saved to: `result_dir'/'"
di as result "  - role_scaling_results.csv"
di as result "  - seniority_scaling_results.csv"  
di as result "  - composition_scaling_summary.csv"
di as result "============================================================"

capture log close
