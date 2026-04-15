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
* composition_irfs_clean_identification.do
* Clean IRF analysis with strongest identification strategy
* - No additional controls (temporal structure solves endogeneity)
* - user_id#firm_id FE for within-worker-firm variation only
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_clean_identification.log", replace text

// Setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs_clean"
capture mkdir "$results"

display "================================================================="
display "CLEAN COMPOSITION IRF ANALYSIS - STRONGEST IDENTIFICATION"
display "================================================================="

*============================================================*
* DATA SETUP
*============================================================*

display _n "STEP 1: Loading and merging data..."

// Load user panel
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
display "User panel loaded: N = " _N

// Load and prepare composition data
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year,half)
    gen companyname_c = lower(companyname)
    
    // Keep key roles for analysis
    keep if inlist(role_k7, "Engineer", "Sales", "Marketing", "Finance", "Operations")
    keep companyname_c yh role_k7 pct_growth_role role_share
    
    // Reshape to wide format
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share* share_*
    
    // Clean missing values (set to 0 for firms without that role)
    foreach var of varlist pct_growth_* share_* {
        replace `var' = 0 if missing(`var')
    }
    
    tempfile role_wide
    save `role_wide'
restore

// Merge with user panel
merge m:1 companyname_c yh using `role_wide'
display "Merge results:"
tab _merge

keep if _merge == 3
drop _merge

display "Final merged dataset: N = " _N

*============================================================*
* PANEL SETUP AND LEAD GENERATION
*============================================================*

display _n "STEP 2: Setting up panel structure and generating leads..."

// Set panel structure
xtset user_id yh
sort user_id yh

// Generate outcome leads for IRF analysis
local max_horizon 4
forvalues h = 0/`max_horizon' {
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
    local missing_h`h' = _N - r(N_created)
    display "  F`h'_prod: \" r(N_created) " observations created, " ///
        `missing_h`h'' " missing due to panel structure"
}

// Check final sample sizes
display _n "Sample sizes by horizon:"
forvalues h = 0/`max_horizon' {
    count if !missing(F`h'_prod, total_contributions_q100)
    display "  Horizon `h': " r(N) " observations"
}

*============================================================*
* CLEAN IRF ESTIMATION - NO CONTROLS
*============================================================*

display _n "STEP 3: Clean IRF estimation (no controls, user#firm FE)..."

// Role growth variables
local role_vars "pct_growth_Engineer pct_growth_Sales pct_growth_Marketing pct_growth_Finance pct_growth_Operations"

// Setup results storage
capture postfile clean_irf_results str15 role horizon coef se tstat pval ///
    ci_lower ci_upper nobs r2 using "$results/clean_irf_estimates.dta", replace

// Joint sample size check
count if !missing(pct_growth_Engineer, pct_growth_Sales, pct_growth_Marketing, ///
    pct_growth_Finance, pct_growth_Operations, total_contributions_q100, F`max_horizon'_prod)
local joint_sample = r(N)
display "Joint sample for full IRF: " `joint_sample'

// Run clean IRF estimation
forvalues h = 0/`max_horizon' {
    display _n "--- Estimating Horizon `h' (Clean Identification) ---"
    
    // Clean specification: future productivity on current composition growth
    // Using user#firm FE to identify within-worker-firm variation only
    capture reghdfe F`h'_prod `role_vars', ///
        absorb(user_id#firm_id yh) vce(cluster user_id)
    
    if _rc == 0 {
        local N_h = e(N)
        local r2_h = e(r2)
        display "  Sample size: " `N_h'
        display "  R-squared: " %5.3f `r2_h'
        
        // Store results for each role
        foreach var of local role_vars {
            local role_name = subinstr("`var'", "pct_growth_", "", .)
            
            // Extract coefficient and statistics
            local b = _b[`var']
            local se = _se[`var']
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            local ci_lower = `b' - invttail(e(df_r), 0.025) * `se'
            local ci_upper = `b' + invttail(e(df_r), 0.025) * `se'
            
            // Store in results file
            post clean_irf_results ("`role_name'") (`h') (`b') (`se') (`t') (`pval') ///
                (`ci_lower') (`ci_upper') (`N_h') (`r2_h')
            
            // Display with significance stars
            local stars ""
            if `pval' < 0.01 local stars "***"
            else if `pval' < 0.05 local stars "**"
            else if `pval' < 0.10 local stars "*"
            
            display "    `role_name': β=" %7.4f `b' " (se=" %6.4f `se' ") `stars'"
        }
        
        // Joint F-test for all composition variables
        capture test `role_vars'
        if _rc == 0 {
            display "    Joint F-test: F=" %6.2f r(F) " p-value=" %6.4f r(p)
        }
    }
    else {
        display "  ESTIMATION FAILED for horizon `h'"
        // Store missing values
        foreach var of local role_vars {
            local role_name = subinstr("`var'", "pct_growth_", "", .)
            post clean_irf_results ("`role_name'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
        }
    }
}

postclose clean_irf_results

*============================================================*
* RESULTS PROCESSING AND COMPARISON
*============================================================*

display _n "STEP 4: Processing clean results..."

// Load results for processing
use "$results/clean_irf_estimates.dta", clear

// Create coefficient matrix for easy access
reshape wide coef se tstat pval ci_lower ci_upper nobs r2, i(role) j(horizon)

// Export to CSV
export delimited using "$results/clean_irf_results.csv", replace

// Create formatted table
preserve
    // Reshape back to long for table creation
    reshape long coef se tstat pval ci_lower ci_upper nobs r2, i(role) j(horizon)
    
    // Create formatted coefficient strings with stars
    gen coef_string = string(coef, "%7.4f")
    gen se_string = "(" + string(se, "%6.4f") + ")"
    
    // Add significance stars
    replace coef_string = coef_string + "***" if pval < 0.01 & !missing(pval)
    replace coef_string = coef_string + "**" if pval >= 0.01 & pval < 0.05 & !missing(pval)
    replace coef_string = coef_string + "*" if pval >= 0.05 & pval < 0.10 & !missing(pval)
    
    // Export formatted table
    keep role horizon coef_string se_string nobs
    reshape wide coef_string se_string nobs, i(role) j(horizon)
    
    export delimited using "$results/clean_irf_table_formatted.csv", replace
    display "Clean formatted table saved to: $results/clean_irf_table_formatted.csv"
restore

*============================================================*
* CLEAN GRAPHICAL ANALYSIS
*============================================================*

display _n "STEP 5: Creating clean IRF graphs..."

// Load results data for graphing
use "$results/clean_irf_estimates.dta", clear

// Create individual IRF plots for each role
levelsof role, local(roles)
foreach role of local roles {
    preserve
        keep if role == "`role'"
        
        // Create clean IRF plot with confidence intervals
        twoway (rcap ci_lower ci_upper horizon, lcolor(gs10)) ///
               (connected coef horizon, lcolor(navy) mcolor(navy) lwidth(thick)), ///
               yline(0, lpattern(dash) lcolor(gs8)) ///
               xlabel(0(1)`max_horizon', labsize(medium)) ///
               xtitle("Horizon (6-month periods)", size(medium)) ///
               ytitle("Effect on Productivity Percentile", size(medium)) ///
               title("Clean IRF: `role' Hiring → Individual Productivity", size(large)) ///
               subtitle("User×Firm FE, no controls - identifying within-worker-firm variation", size(medium)) ///
               legend(off) ///
               graphregion(color(white)) plotregion(color(white))
        
        graph export "$results/clean_irf_`role'.png", replace width(800) height(600)
        display "Clean individual IRF saved: $results/clean_irf_`role'.png"
    restore
}

// Create combined IRF plot
display _n "Creating clean combined IRF plot..."

// Define colors and markers for each role
local colors "navy maroon forest_green dkorange purple"
local markers "circle diamond triangle square plus"

// Build combined plot command
local plot_cmd ""
local legend_labels ""
local role_counter = 1

foreach role of local roles {
    local color : word `role_counter' of `colors'
    local marker : word `role_counter' of `markers'
    
    if `role_counter' > 1 local plot_cmd "`plot_cmd' || "
    local plot_cmd "`plot_cmd' (connected coef horizon if role=="`role'", "
    local plot_cmd "`plot_cmd' lcolor(`color') mcolor(`color') msymbol(`marker') lwidth(medthick))"
    
    local legend_labels "`legend_labels' `role_counter' \"`role'""
    local ++role_counter
}

// Create clean combined plot
twoway `plot_cmd', ///
    yline(0, lpattern(dash) lcolor(gs8)) ///
    xlabel(0(1)`max_horizon', labsize(medium)) ///
    xtitle("Horizon (6-month periods)", size(medium)) ///
    ytitle("Effect on Productivity Percentile", size(medium)) ///
    title("Clean Productivity IRFs by Role Hiring", size(large)) ///
    subtitle("User×Firm FE identification - no controls", size(medium)) ///
    legend(label(`legend_labels') cols(3) size(medium)) ///
    graphregion(color(white)) plotregion(color(white))

graph export "$results/clean_irf_combined.png", replace width(1000) height(700)
display "Clean combined IRF saved: $results/clean_irf_combined.png"

*============================================================*
* SUMMARY
*============================================================*

display _n _n "================================================================="
display "CLEAN IRF ANALYSIS COMPLETE"
display "================================================================="

display _n "Clean identification strategy:"
display "  - Future productivity regressed on current composition growth"
display "  - User×Firm fixed effects (within-worker-firm variation only)"
display "  - No additional controls (temporal structure solves endogeneity)"
display "  - Standard errors clustered at user level"

display _n "Files created in $results/:"
display "  - clean_irf_estimates.dta: Raw clean IRF estimates"
display "  - clean_irf_results.csv: Clean results in CSV format"
display "  - clean_irf_table_formatted.csv: Publication-ready clean table"
display "  - clean_irf_combined.png: Clean combined IRF plot"
display "  - clean_irf_[Role].png: Clean individual IRF plots by role"

display _n "Key insight:"
display "  - Temporal structure (leads) eliminates reverse causality"
display "  - User×Firm FE controls for all time-invariant confounders"
display "  - Time FE controls for common shocks and anticipatory trends"
display "  - Remaining variation is quasi-experimental composition shocks"

log close

display _n "Clean analysis log saved to: composition_irfs_clean_identification.log"
display "================================================================="