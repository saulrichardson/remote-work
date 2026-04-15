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
* create_combined_irf.do
* Create the missing combined IRF plot
*============================================================*

clear all
set more off

global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs"

// Load IRF results
use "$results/irf_estimates.dta", clear

// Create combined IRF plot showing all roles
display "Creating combined IRF plot..."

// Define colors and markers for each role
local colors "navy maroon forest_green dkorange purple"
local markers "circle diamond triangle square plus"

// Get list of roles
levelsof role, local(roles)
local role_counter = 1

// Build combined plot command
local plot_cmd ""
local legend_labels ""

foreach role of local roles {
    local color : word `role_counter' of `colors'
    local marker : word `role_counter' of `markers'
    
    if `role_counter' > 1 local plot_cmd "`plot_cmd' || "
    local plot_cmd "`plot_cmd' (connected coef horizon if role=="`role'", "
    local plot_cmd "`plot_cmd' lcolor(`color') mcolor(`color') msymbol(`marker') lwidth(medthick))"
    
    local legend_labels "`legend_labels' `role_counter' \"`role'""
    local ++role_counter
}

// Create combined plot
twoway `plot_cmd', ///
    yline(0, lpattern(dash) lcolor(gs8)) ///
    xlabel(0(1)4, labsize(medium)) ///
    xtitle("Horizon (6-month periods)", size(medium)) ///
    ytitle("Effect on Productivity Percentile", size(medium)) ///
    title("Productivity IRFs by Role Hiring", size(large)) ///
    subtitle("Multi-variable estimation controlling for all roles simultaneously", size(medium)) ///
    legend(label(`legend_labels') cols(3) size(medium)) ///
    graphregion(color(white)) plotregion(color(white))

graph export "$results/irf_combined.png", replace width(1000) height(700)
display "Combined IRF saved: $results/irf_combined.png"