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
*  firm_scaling_composition_simple.do
*  — Scaling regressions by role and seniority level
*============================================================*

clear all
set more off

// Set paths
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

// Setup log
local specname "firm_scaling_composition"
capture log close
log using "`specname'_simple.log", replace text

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

display "Starting composition scaling analysis..."

*============================================================*
* PART A: Role-based scaling regressions
*============================================================*

// 1) Load and prepare firm panel data
use "$processed_data/firm_panel.dta", clear
display "Loaded firm panel with `=_N' observations"

// Keep only needed variables to save memory
keep firm_id companyname yh year half covid remote teleworkable

// Generate interaction variables (matching firm_scaling.do)
gen var3 = covid * remote        // covid*remote
gen var4 = covid                 // covid
gen var5 = covid * teleworkable  // covid*teleworkable
gen var6 = teleworkable          // teleworkable (instrument)
gen var7 = teleworkable * covid  // teleworkable*covid (instrument)

tempfile firm_data
save `firm_data'

// 2) Process role growth data
display _n "Processing role growth data..."
import delimited "$processed_data/role_k7_scaling_growth.csv", clear
display "Loaded role data with `=_N' observations"

// Clean role names
replace role_k7 = trim(role_k7)
replace role_k7 = subinstr(role_k7, " ", "", .)
replace role_k7 = subinstr(role_k7, `"""', "", .)

// Show unique roles
tab role_k7

// Keep valid roles only
keep if inlist(role_k7, "Admin", "Engineer", "Finance", "Marketing", "Operations", "Sales", "Scientist")

// Create year-half to match firm panel
gen yh = year * 10 + half

// Prepare for reshape
rename pct_growth_role growth_
keep companyname role_k7 yh growth_

// Reshape to wide
reshape wide growth_, i(companyname yh) j(role_k7) string
display "After reshape: `=_N' company-halfyear observations"

// Merge with firm data
merge 1:1 companyname yh using `firm_data'
keep if _merge == 3
drop _merge
display "After merge with firm panel: `=_N' observations"

// Store results
tempfile results_role
gen outcome_type = "role"
save `results_role'

// 3) Run role regressions
local roles "Admin Engineer Finance Marketing Operations Sales Scientist"

display _n "Running role scaling regressions..."
display "=" * 60

foreach role of local roles {
    capture confirm variable growth_`role'
    if _rc == 0 {
        display _n "→ Processing growth_`role'"
        
        // Count non-missing
        count if !missing(growth_`role')
        local n_nonmiss = r(N)
        display "   Non-missing observations: `n_nonmiss'"
        
        if `n_nonmiss' > 100 {
            // Pre-COVID mean
            qui sum growth_`role' if covid == 0
            local pre_mean = r(mean)
            display "   Pre-COVID mean: " %6.4f `pre_mean'
            
            // OLS
            reghdfe growth_`role' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
            
            // Store OLS results
            matrix b = e(b)
            matrix V = e(V)
            local b_var3 = b[1,1]
            local se_var3 = sqrt(V[1,1])
            local t_var3 = `b_var3'/`se_var3'
            local p_var3 = 2*ttail(e(df_r), abs(`t_var3'))
            
            display "   OLS coefficient on var3 (covid*remote): " %6.4f `b_var3' " (p=" %4.3f `p_var3' ")"
            
            // Save to dataset
            preserve
            clear
            set obs 1
            gen outcome = "growth_`role'"
            gen model = "OLS"
            gen coef_var3 = `b_var3'
            gen se_var3 = `se_var3'
            gen p_var3 = `p_var3'
            gen pre_mean = `pre_mean'
            gen nobs = e(N)
            save "$results/`specname'/role_`role'_ols.dta", replace
            restore
        }
    }
}

*============================================================*
* PART B: Seniority-based scaling regressions  
*============================================================*

// 4) Process seniority growth data
use `firm_data', clear

display _n "Processing seniority growth data..."
import delimited "$processed_data/seniority_scaling_growth.csv", clear
display "Loaded seniority data with `=_N' observations"

// Create year-half
gen yh = year * 10 + half

// Create seniority label
gen sen_label = "sen" + string(seniority_level)

// Prepare for reshape
rename pct_growth_seniority growth_
keep companyname sen_label yh growth_

// Reshape to wide
reshape wide growth_, i(companyname yh) j(sen_label) string
display "After reshape: `=_N' company-halfyear observations"

// Merge with firm data
merge 1:1 companyname yh using `firm_data'
keep if _merge == 3
drop _merge
display "After merge with firm panel: `=_N' observations"

// 5) Run seniority regressions
local seniority_levels "sen1 sen2 sen3 sen4"

display _n "Running seniority scaling regressions..."
display "=" * 60

foreach sen of local seniority_levels {
    capture confirm variable growth_`sen'
    if _rc == 0 {
        display _n "→ Processing growth_`sen'"
        
        count if !missing(growth_`sen')
        local n_nonmiss = r(N)
        display "   Non-missing observations: `n_nonmiss'"
        
        if `n_nonmiss' > 100 {
            // Pre-COVID mean
            qui sum growth_`sen' if covid == 0
            local pre_mean = r(mean)
            display "   Pre-COVID mean: " %6.4f `pre_mean'
            
            // OLS
            reghdfe growth_`sen' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
            
            // Store results
            matrix b = e(b)
            matrix V = e(V)
            local b_var3 = b[1,1]
            local se_var3 = sqrt(V[1,1])
            local t_var3 = `b_var3'/`se_var3'
            local p_var3 = 2*ttail(e(df_r), abs(`t_var3'))
            
            display "   OLS coefficient on var3 (covid*remote): " %6.4f `b_var3' " (p=" %4.3f `p_var3' ")"
            
            // Save to dataset
            preserve
            clear
            set obs 1
            gen outcome = "growth_`sen'"
            gen model = "OLS"
            gen coef_var3 = `b_var3'
            gen se_var3 = `se_var3'
            gen p_var3 = `p_var3'
            gen pre_mean = `pre_mean'
            gen nobs = e(N)
            save "$results/`specname'/seniority_`sen'_ols.dta", replace
            restore
        }
    }
}

display _n "=" * 60
display "Composition scaling analysis complete!"
display "Results saved to: $results/`specname'/"

log close