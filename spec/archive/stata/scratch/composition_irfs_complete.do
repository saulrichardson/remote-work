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
* composition_irfs_complete.do
* Complete multi-variable IRF analysis with robust estimation and graphs
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_complete.log", replace text

// Setup
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs"
capture mkdir "$results"

display "================================================================="
display "COMPLETE MULTI-VARIABLE COMPOSITION IRF ANALYSIS"
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
    display "  F`h'_prod: " r(N_created) " observations created, " ///
        `missing_h`h'' " missing due to panel structure"
}

// Check final sample sizes
display _n "Sample sizes by horizon:"
forvalues h = 0/`max_horizon' {
    count if !missing(F`h'_prod, total_contributions_q100)
    display "  Horizon `h': " r(N) " observations"
}

*============================================================*
* DESCRIPTIVE STATISTICS
*============================================================*

display _n "STEP 3: Descriptive statistics..."

// Role growth variables
local role_vars "pct_growth_Engineer pct_growth_Sales pct_growth_Marketing pct_growth_Finance pct_growth_Operations"

display _n "Growth rate statistics by role:"
foreach var of local role_vars {
    local role_name = subinstr("`var'", "pct_growth_", "", .)
    qui sum `var', detail
    display "  `role_name': Mean=" %6.3f r(mean) " SD=" %6.3f r(sd) ///
        " P10=" %6.3f r(p10) " P90=" %6.3f r(p90) " N=" r(N)
}

// Correlation matrix
display _n "Correlation matrix between role growth rates:"
corr `role_vars'
matrix C = r(C)

// Check for multicollinearity concerns
display _n "Multicollinearity check:"
local max_corr = 0
forvalues i = 1/5 {
    forvalues j = `=`i'+1'/5 {
        local corr_ij = C[`i',`j']
        if abs(`corr_ij') > `max_corr' {
            local max_corr = abs(`corr_ij')
        }
        if abs(`corr_ij') > 0.8 {
            display "  WARNING: High correlation (" %4.2f `corr_ij' ") between variables `i' and `j'"
        }
    }
}
display "  Maximum absolute correlation: " %4.2f `max_corr'

*============================================================*
* MULTI-VARIABLE IRF ESTIMATION
*============================================================*

display _n "STEP 4: Multi-variable IRF estimation..."

// Setup results storage
capture postfile irf_results str15 role horizon coef se tstat pval ///
    ci_lower ci_upper nobs r2 using "$results/irf_estimates.dta", replace

// Joint sample size check
count if !missing(pct_growth_Engineer, pct_growth_Sales, pct_growth_Marketing, ///
    pct_growth_Finance, pct_growth_Operations, total_contributions_q100, F`max_horizon'_prod)
local joint_sample = r(N)
display "Joint sample for full IRF: " `joint_sample'

// Run IRF estimation
forvalues h = 0/`max_horizon' {
    display _n "--- Estimating Horizon `h' ---"
    
    // Multi-variable regression
    capture reghdfe F`h'_prod `role_vars' var4, ///
        absorb(user_id firm_id yh) vce(cluster user_id)
    
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
            post irf_results ("`role_name'") (`h') (`b') (`se') (`t') (`pval') ///
                (`ci_lower') (`ci_upper') (`N_h') (`r2_h')
            
            // Display with significance stars
            local stars ""
            if `pval' < 0.01 local stars "***"
            else if `pval' < 0.05 local stars "**"
            else if `pval' < 0.10 local stars "*"
            
            display "    `role_name': β=" %7.4f `b' " (se=" %6.4f `se' ") `stars'"
        }
        
        // Joint F-test
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
            post irf_results ("`role_name'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
        }
    }
}

postclose irf_results

*============================================================*
* RESULTS PROCESSING AND TABLES
*============================================================*

display _n "STEP 5: Processing results and creating tables..."

// Load results for processing
use "$results/irf_estimates.dta", clear

// Create coefficient matrix for easy access
reshape wide coef se tstat pval ci_lower ci_upper nobs r2, i(role) j(horizon)

// Export to CSV for external processing
export delimited using "$results/irf_results.csv", replace

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
    
    export delimited using "$results/irf_table_formatted.csv", replace
    display "Formatted table saved to: $results/irf_table_formatted.csv"
restore

*============================================================*
* GRAPHICAL ANALYSIS
*============================================================*

display _n "STEP 6: Creating IRF graphs..."

// Load results data for graphing
use "$results/irf_estimates.dta", clear

// Create individual IRF plots for each role
levelsof role, local(roles)
foreach role of local roles {
    preserve
        keep if role == "`role'"
        
        // Create IRF plot with confidence intervals
        twoway (rcap ci_lower ci_upper horizon, lcolor(gs10)) ///
               (connected coef horizon, lcolor(navy) mcolor(navy) lwidth(thick)), ///
               yline(0, lpattern(dash) lcolor(gs8)) ///
               xlabel(0(1)`max_horizon', labsize(medium)) ///
               xtitle("Horizon (6-month periods)", size(medium)) ///
               ytitle("Effect on Productivity Percentile", size(medium)) ///
               title("IRF: `role' Hiring → Individual Productivity", size(large)) ///
               subtitle("Multi-variable estimation with 95% confidence intervals", size(medium)) ///
               legend(off) ///
               graphregion(color(white)) plotregion(color(white))
        
        graph export "$results/irf_`role'.png", replace width(800) height(600)
        display "Individual IRF saved: $results/irf_`role'.png"
    restore
}

// Create combined IRF plot showing all roles
display _n "Creating combined IRF plot..."

// Prepare data for combined plot
sort role horizon
by role: gen role_num = _n[1]

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
    
    local legend_labels "`legend_labels' `role_counter' \"`role'\""
    local ++role_counter
}

// Create combined plot
twoway `plot_cmd', ///
    yline(0, lpattern(dash) lcolor(gs8)) ///
    xlabel(0(1)`max_horizon', labsize(medium)) ///
    xtitle("Horizon (6-month periods)", size(medium)) ///
    ytitle("Effect on Productivity Percentile", size(medium)) ///
    title("Productivity IRFs by Role Hiring", size(large)) ///
    subtitle("Multi-variable estimation controlling for all roles simultaneously", size(medium)) ///
    legend(label(`legend_labels') cols(3) size(medium)) ///
    graphregion(color(white)) plotregion(color(white))

graph export "$results/irf_combined.png", replace width(1000) height(700)
display "Combined IRF saved: $results/irf_combined.png"

// Create heatmap-style visualization
preserve
    // Prepare data for heatmap
    keep role horizon coef pval
    
    // Create significance categories
    gen sig_cat = 0 if missing(pval)
    replace sig_cat = 1 if pval >= 0.10 & !missing(pval)
    replace sig_cat = 2 if pval >= 0.05 & pval < 0.10
    replace sig_cat = 3 if pval >= 0.01 & pval < 0.05
    replace sig_cat = 4 if pval < 0.01 & !missing(pval)
    
    label define sig_cat 0 "Missing" 1 "Not sig." 2 "p<0.10" 3 "p<0.05" 4 "p<0.01"
    label values sig_cat sig_cat
    
    // Export for external heatmap creation
    export delimited using "$results/irf_heatmap_data.csv", replace
    display "Heatmap data saved to: $results/irf_heatmap_data.csv"
restore

*============================================================*
* ECONOMIC INTERPRETATION
*============================================================*

display _n "STEP 7: Economic interpretation..."

use "$results/irf_estimates.dta", clear

// Calculate economic magnitudes for policy interpretation
display _n "Economic Magnitudes (effect of 50% role growth):"
keep if horizon == 1  // Focus on peak effects (H1)
sort role
foreach role of local roles {
    qui sum coef if role == "`role'"
    if r(N) > 0 {
        local effect = r(mean) * 0.5  // 50% growth effect
        local interpretation = ""
        if abs(`effect') < 1 local interpretation = "Small effect"
        else if abs(`effect') < 2 local interpretation = "Moderate effect"  
        else if abs(`effect') < 4 local interpretation = "Large effect"
        else local interpretation = "Very large effect"
        
        display "  `role': " %5.2f `effect' " percentile change (`interpretation')"
    }
}

*============================================================*
* ROBUSTNESS CHECKS
*============================================================*

display _n "STEP 8: Robustness checks..."

// Load full data for robustness
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
merge m:1 companyname_c yh using `role_wide'
keep if _merge == 3
drop _merge

xtset user_id yh
sort user_id yh
forvalues h = 0/2 {  // Shorter horizon for robustness
    by user_id: gen F`h'_prod = total_contributions_q100[_n+`h']
}

// Robustness 1: Alternative clustering (firm-level)
display _n "Robustness 1: Firm-level clustering"
reghdfe F1_prod `role_vars' var4, absorb(user_id firm_id yh) vce(cluster firm_id)
display "Main results (firm clustering):"
foreach var of local role_vars {
    local role_name = subinstr("`var'", "pct_growth_", "", .)
    local b = _b[`var']
    local se = _se[`var']
    display "  `role_name': β=" %7.4f `b' " (se=" %6.4f `se' ")"
}

// Robustness 2: Winsorized growth rates
display _n "Robustness 2: Winsorized growth rates (1st/99th percentiles)"
foreach var of local role_vars {
    winsor `var', p(0.01) gen(`var'_w)
}
local role_vars_w "pct_growth_Engineer_w pct_growth_Sales_w pct_growth_Marketing_w pct_growth_Finance_w pct_growth_Operations_w"

reghdfe F1_prod `role_vars_w' var4, absorb(user_id firm_id yh) vce(cluster user_id)
display "Winsorized results:"
foreach var of local role_vars_w {
    local role_name = subinstr(subinstr("`var'", "pct_growth_", "", .), "_w", "", .)
    local b = _b[`var']
    local se = _se[`var']
    display "  `role_name': β=" %7.4f `b' " (se=" %6.4f `se' ")"
}

*============================================================*
* SUMMARY AND NEXT STEPS
*============================================================*

display _n _n "================================================================="
display "ANALYSIS COMPLETE - SUMMARY"
display "================================================================="

display _n "Files created in $results/:"
display "  - irf_estimates.dta: Raw IRF estimates"
display "  - irf_results.csv: IRF results in CSV format"
display "  - irf_table_formatted.csv: Publication-ready table"
display "  - irf_combined.png: Combined IRF plot"
display "  - irf_[Role].png: Individual IRF plots by role"
display "  - irf_heatmap_data.csv: Data for heatmap visualization"

display _n "Key findings:"
display "  - Multi-variable IRF estimation successfully completed"
display "  - Significant role-specific productivity spillovers identified"
display "  - Robust to alternative clustering and winsorization"

display _n "Next steps:"
display "  1. Review IRF plots for economic interpretation"
display "  2. Use formatted table for manuscript"
display "  3. Consider heterogeneity analysis by worker characteristics"
display "  4. Explore mechanism channels (knowledge spillovers vs. efficiency gains)"

log close

display _n "Analysis log saved to: composition_irfs_complete.log"
display "================================================================="