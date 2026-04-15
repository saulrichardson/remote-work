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
* create_clean_graphs.do
* Create properly formatted individual and combined IRF graphs
*============================================================*

clear all
set more off

global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs_all7"

// Load results data
use "$results/all7_irf_estimates.dta", clear

display "Creating individual IRF graphs for all 7 roles..."

*============================================================*
* INDIVIDUAL GRAPHS FOR EACH ROLE
*============================================================*

levelsof role, local(roles)
foreach role of local roles {
    preserve
        keep if role == "`role'"
        
        // Create clean individual IRF plot
        twoway (rcap ci_lower ci_upper horizon, lcolor(gs10) lwidth(medium)) ///
               (connected coef horizon, lcolor(navy) mcolor(navy) ///
                msymbol(circle) msize(medium) lwidth(thick)), ///
               yline(0, lpattern(dash) lcolor(gs8)) ///
               xlabel(0(1)4, labsize(medium)) ///
               ylabel(, labsize(medium) format(%4.1f)) ///
               xtitle("Horizon (6-month periods)", size(medium)) ///
               ytitle("Effect on Productivity Percentile", size(medium)) ///
               title("IRF: `role' Hiring → Individual Productivity", size(large)) ///
               subtitle("User×Firm FE identification with 95% confidence intervals", size(medium)) ///
               legend(off) ///
               graphregion(color(white)) plotregion(color(white)) ///
               scheme(s1color)
        
        graph export "$results/clean_irf_`role'.png", replace width(800) height(600)
        display "Individual IRF saved: clean_irf_`role'.png"
    restore
}

*============================================================*
* CLEAN COMBINED GRAPH
*============================================================*

display _n "Creating properly formatted combined IRF graph..."

// Define distinct colors for 7 roles
local colors `""navy" "maroon" "forest_green" "dkorange" "purple" "cranberry" "blue""'
local markers `""circle" "diamond" "triangle" "square" "plus" "x" "smcircle""'

// Build the plot command properly
local plot_cmd ""
local legend_labels ""
local role_counter = 1

foreach role of local roles {
    local color : word `role_counter' of `colors'
    local marker : word `role_counter' of `markers'
    
    if `role_counter' > 1 {
        local plot_cmd "`plot_cmd' || "
    }
    
    local plot_cmd "`plot_cmd' (connected coef horizon if role=="`role'", "
    local plot_cmd "`plot_cmd' lcolor(`color') mcolor(`color') msymbol(`marker') "
    local plot_cmd "`plot_cmd' msize(medium) lwidth(medthick))"
    
    local legend_labels "`legend_labels' `role_counter' "`role'" "
    local ++role_counter
}

// Create properly formatted combined plot
twoway `plot_cmd', ///
    yline(0, lpattern(dash) lcolor(gs8)) ///
    xlabel(0(1)4, labsize(medium)) ///
    ylabel(, labsize(medium) format(%4.1f)) ///
    xtitle("Horizon (6-month periods)", size(medium)) ///
    ytitle("Effect on Productivity Percentile", size(medium)) ///
    title("Productivity IRFs by Role Hiring", size(large)) ///
    subtitle("All 7 roles with User×Firm FE identification", size(medium)) ///
    legend(order(`legend_labels') cols(4) size(small) position(6) ///
           region(color(white)) bmargin(small)) ///
    graphregion(color(white)) plotregion(color(white)) ///
    scheme(s1color)

graph export "$results/clean_combined_all7.png", replace width(1200) height(800)
display "Clean combined IRF saved: clean_combined_all7.png"

*============================================================*
* CREATE FOCUSED SUBSETS
*============================================================*

display _n "Creating focused subset graphs..."

// High-impact roles: Engineer, Sales, Scientist
preserve
    keep if inlist(role, "Engineer", "Sales", "Scientist")
    
    local plot_cmd ""
    local legend_labels ""
    local role_counter = 1
    local colors_sub `""navy" "maroon" "forest_green""'
    local markers_sub `""circle" "diamond" "triangle""'
    
    levelsof role, local(roles_sub)
    foreach role of local roles_sub {
        local color : word `role_counter' of `colors_sub'
        local marker : word `role_counter' of `markers_sub'
        
        if `role_counter' > 1 {
            local plot_cmd "`plot_cmd' || "
        }
        
        local plot_cmd "`plot_cmd' (connected coef horizon if role=="`role'", "
        local plot_cmd "`plot_cmd' lcolor(`color') mcolor(`color') msymbol(`marker') "
        local plot_cmd "`plot_cmd' msize(medium) lwidth(thick))"
        
        local legend_labels "`legend_labels' `role_counter' "`role'" "
        local ++role_counter
    }
    
    twoway `plot_cmd', ///
        yline(0, lpattern(dash) lcolor(gs8)) ///
        xlabel(0(1)4, labsize(medium)) ///
        ylabel(, labsize(medium) format(%4.1f)) ///
        xtitle("Horizon (6-month periods)", size(medium)) ///
        ytitle("Effect on Productivity Percentile", size(medium)) ///
        title("High-Impact Role IRFs", size(large)) ///
        subtitle("Engineer, Sales, and Scientist hiring effects", size(medium)) ///
        legend(order(`legend_labels') cols(3) size(medium) position(6) ///
               region(color(white))) ///
        graphregion(color(white)) plotregion(color(white)) ///
        scheme(s1color)
    
    graph export "$results/high_impact_roles.png", replace width(1000) height(700)
    display "High-impact roles IRF saved: high_impact_roles.png"
restore

*============================================================*
* SUMMARY TABLE WITH PROPER FORMATTING
*============================================================*

display _n "Creating clean summary table..."

// Create a clean text summary
preserve
    keep role horizon coef pval
    
    // Add significance indicators
    gen sig_level = ""
    replace sig_level = "***" if pval < 0.01 & !missing(pval)
    replace sig_level = "**" if pval >= 0.01 & pval < 0.05 & !missing(pval)  
    replace sig_level = "*" if pval >= 0.05 & pval < 0.10 & !missing(pval)
    
    // Reshape for table format
    gen coef_formatted = string(coef, "%6.3f") + sig_level
    keep role horizon coef_formatted
    reshape wide coef_formatted, i(role) j(horizon)
    
    // Order roles logically
    gen role_order = .
    replace role_order = 1 if role == "Engineer"
    replace role_order = 2 if role == "Sales"  
    replace role_order = 3 if role == "Scientist"
    replace role_order = 4 if role == "Operations"
    replace role_order = 5 if role == "Finance"
    replace role_order = 6 if role == "Marketing"
    replace role_order = 7 if role == "Admin"
    
    sort role_order
    
    export delimited using "$results/clean_summary_table.csv", replace
    display "Clean summary table saved: clean_summary_table.csv"
restore

display _n _n "================================================================="
display "CLEAN GRAPH CREATION COMPLETE"
display "================================================================="

display _n "Files created:"
display "Individual graphs:"
local roles2 "Admin Engineer Finance Marketing Operations Sales Scientist"
foreach role of local roles2 {
    display "  - clean_irf_`role'.png"
}

display _n "Combined graphs:"
display "  - clean_combined_all7.png (all 7 roles, properly formatted)"  
display "  - high_impact_roles.png (Engineer, Sales, Scientist focus)"

display _n "Data files:"
display "  - clean_summary_table.csv (properly formatted results table)"

display _n "All files saved in: $results/"
display "================================================================="