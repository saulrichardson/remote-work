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

*=============================================================================*
* Full Scaling Regressions with Pre-COVID Composition
* This script implements the complete specification for role × seniority analysis
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Load and merge data
*-----------------------------------------------------------------------------*

* Load firm panel
use "$processed_data/firm_panel.dta", clear

* Create lowercase company name for merging
gen companyname_lower = lower(companyname)

* Keep COVID period only
keep if covid == 1

* Merge with pre-COVID composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

* Check merge success
count
local N = r(N)
di "Firms in COVID period with composition data: `N'"

* Summary statistics
summarize growth_rate_we startup engineer_share_2019 sales_share_2019 level1_share_2019 level2_share_2019

*-----------------------------------------------------------------------------*
* Part 2: Define controls and variable lists
*-----------------------------------------------------------------------------*

* Standard controls
local controls "age rent hhi_1000 i.yh"

* Role variables (7 roles)
local roles "engineer sales finance marketing admin operations scientist"

* Seniority variables (4 levels)
local seniority "level1 level2 level3 level4"

*-----------------------------------------------------------------------------*
* Part 3: Run full set of regressions
*-----------------------------------------------------------------------------*

* Clear any existing estimates
estimates clear

* Column 1: Baseline
eststo baseline: reg growth_rate_we startup `controls', robust

* Store baseline startup coefficient for comparison
local base_startup = _b[startup]
local base_startup_se = _se[startup]

*-----------------------------------------------------------------------------*
* Columns 2-8: Role composition effects
*-----------------------------------------------------------------------------*

local col = 2
foreach role of local roles {
    
    * Run regression with role share and interaction
    eststo col`col': reg growth_rate_we startup ///
        `role'_share_2019 ///
        c.startup#c.`role'_share_2019 ///
        `controls', robust
    
    * Store key results for summary
    local b_`role' = _b[`role'_share_2019]
    local se_`role' = _se[`role'_share_2019]
    local b_int_`role' = _b[c.startup#c.`role'_share_2019]
    local se_int_`role' = _se[c.startup#c.`role'_share_2019]
    
    * Calculate total effect for startups (main + interaction)
    local total_`role' = `b_`role'' + `b_int_`role''
    
    local col = `col' + 1
}

*-----------------------------------------------------------------------------*
* Columns 9-12: Seniority composition effects
*-----------------------------------------------------------------------------*

foreach sen of local seniority {
    
    * Run regression with seniority share and interaction
    eststo col`col': reg growth_rate_we startup ///
        `sen'_share_2019 ///
        c.startup#c.`sen'_share_2019 ///
        `controls', robust
    
    * Store key results
    local b_`sen' = _b[`sen'_share_2019]
    local se_`sen' = _se[`sen'_share_2019]
    local b_int_`sen' = _b[c.startup#c.`sen'_share_2019]
    local se_int_`sen' = _se[c.startup#c.`sen'_share_2019]
    
    local col = `col' + 1
}

*-----------------------------------------------------------------------------*
* Part 4: Export results tables
*-----------------------------------------------------------------------------*

* Table 1: Role composition effects (Columns 1-8)
esttab baseline col2 col3 col4 col5 col6 col7 col8 ///
    using "$results/scaling_precovid_roles_full.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup *_share_2019 *startup#*) ///
    order(startup *_share_2019 *startup#*) ///
    mtitles("Baseline" "Engineer" "Sales" "Finance" "Marketing" "Admin" "Operations" "Scientist") ///
    stats(N r2, fmt(0 3) labels("Observations" "R-squared")) ///
    nonotes addnotes("Dependent variable: Employment growth rate during COVID period" ///
                     "All regressions include firm age, rent, HHI, and year-half fixed effects" ///
                     "Composition measured as % of workforce in 2019 (pre-COVID)" ///
                     "Standard errors are robust to heteroskedasticity")

* Table 2: Seniority composition effects (Columns 1, 9-12)
esttab baseline col9 col10 col11 col12 ///
    using "$results/scaling_precovid_seniority_full.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(startup level*_share_2019 *startup#*) ///
    order(startup level*_share_2019 *startup#*) ///
    mtitles("Baseline" "Entry (L1)" "Mid/Senior (L2)" "Manager (L3)" "Director+ (L4)") ///
    stats(N r2, fmt(0 3) labels("Observations" "R-squared")) ///
    nonotes addnotes("Dependent variable: Employment growth rate during COVID period" ///
                     "All regressions include firm age, rent, HHI, and year-half fixed effects" ///
                     "Seniority levels: L1=Entry, L2=Mid/Senior, L3=Manager, L4=Director/Executive" ///
                     "Standard errors are robust to heteroskedasticity")

*-----------------------------------------------------------------------------*
* Part 5: Summary of key findings
*-----------------------------------------------------------------------------*

di _n _n "="*70
di "SUMMARY OF KEY FINDINGS"
di "="*70

di _n "Baseline startup effect: " %5.3f `base_startup' " (SE = " %5.3f `base_startup_se' ")"

di _n "Role Composition Effects (10% increase in share):"
di "-"*50
foreach role of local roles {
    di "`role': Main = " %5.3f `b_`role''/10 ", Interaction = " %5.3f `b_int_`role''/10 ///
       ", Total for startups = " %5.3f `total_`role''/10
}

di _n "Seniority Composition Effects (10% increase in share):"
di "-"*50
foreach sen of local seniority {
    di "`sen': Main = " %5.3f `b_`sen''/10 ", Interaction = " %5.3f `b_int_`sen''/10
}

*-----------------------------------------------------------------------------*
* Part 6: Additional robustness checks
*-----------------------------------------------------------------------------*

* Check 1: Are results driven by very small/large firms?
preserve
    drop if total_employees_2019 < 50 | total_employees_2019 > 10000
    
    reg growth_rate_we startup engineer_share_2019 c.startup#c.engineer_share_2019 `controls', robust
    di _n "Robustness check (50-10000 employees): Startup × Engineer interaction = " ///
       %5.3f _b[c.startup#c.engineer_share_2019]
restore

* Check 2: Control for pre-COVID growth
gen growth_pre = .  // This would normally come from pre-COVID data
capture {
    reg growth_rate_we startup engineer_share_2019 c.startup#c.engineer_share_2019 ///
        growth_pre `controls', robust
}

* Check 3: Industry heterogeneity
capture {
    reg growth_rate_we startup engineer_share_2019 c.startup#c.engineer_share_2019 ///
        `controls' i.industry, robust cluster(industry)
}

*-----------------------------------------------------------------------------*
* Part 7: Visualization
*-----------------------------------------------------------------------------*

* Create marginal effects plot for engineers
quietly margins, at(engineer_share_2019=(0(10)100) startup=(0 1))
marginsplot, ///
    title("Growth Rate by Engineer Share and Startup Status") ///
    ytitle("Predicted Growth Rate") ///
    xtitle("% Engineers (2019)") ///
    legend(order(1 "Established Firms" 2 "Startups")) ///
    name(eng_margins, replace)

graph export "$results/engineer_composition_margins.png", replace

* Create coefficient plot comparing role effects
preserve
    clear
    set obs 7
    gen role = _n
    gen coef = .
    gen se = .
    gen role_name = ""
    
    local i = 1
    foreach r of local roles {
        replace coef = `b_int_`r'' in `i'
        replace se = `se_int_`r'' in `i'
        replace role_name = "`r'" in `i'
        local i = `i' + 1
    }
    
    gen ci_low = coef - 1.96*se
    gen ci_high = coef + 1.96*se
    
    twoway (scatter coef role) ///
           (rcap ci_low ci_high role), ///
        xlabel(1 "Engineer" 2 "Sales" 3 "Finance" 4 "Marketing" 5 "Admin" 6 "Operations" 7 "Scientist", angle(45)) ///
        ylabel(, format(%5.3f)) ///
        yline(0, lcolor(red) lpattern(dash)) ///
        xtitle("Role") ytitle("Startup × Role Interaction Coefficient") ///
        title("Differential Scaling Effects by Role Composition") ///
        legend(off) ///
        name(role_coef, replace)
        
    graph export "$results/role_composition_coefficients.png", replace
restore

di _n _n "Analysis complete. Results saved to:"
di "  - $results/scaling_precovid_roles_full.tex"
di "  - $results/scaling_precovid_seniority_full.tex"
di "  - $results/engineer_composition_margins.png"
di "  - $results/role_composition_coefficients.png"

* Save log file
log using "$results/scaling_precovid_composition_log.txt", replace text
estimates table col*, b(%7.4f) se(%7.4f) stats(N r2)
log close