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
* Full Productivity Regressions with Pre-COVID Composition Controls
* This script tests how firm composition affects remote work effectiveness
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Load and merge data
*-----------------------------------------------------------------------------*

* Load user panel (individual-level data)
use "$processed_data/user_panel_precovid.dta", clear

* Create lowercase company name for merging
gen companyname_lower = lower(companyname)

* Merge with pre-COVID composition data
merge m:1 companyname_lower using "$results/composition_precovid_2019.dta", keep(match) nogen

* Check merge
count
local N = r(N)
di "Individual observations with composition data: `N'"

* Get unique firms for summary
preserve
    duplicates drop companyname, force
    count
    local N_firms = r(N)
restore
di "Number of unique firms: `N_firms'"

*-----------------------------------------------------------------------------*
* Part 2: Create interaction terms
*-----------------------------------------------------------------------------*

* Role variables
local roles "engineer sales finance marketing admin operations scientist"

* Create interaction terms for each role
foreach role of local roles {
    gen var3_`role' = var3 * `role'_share_2019
    gen var5_`role' = var5 * `role'_share_2019
    gen var6_`role' = var6 * `role'_share_2019
    gen var7_`role' = var7 * `role'_share_2019
}

* Seniority variables
local seniority "level1 level2 level3 level4"

* Create interaction terms for each seniority level
foreach sen of local seniority {
    gen var3_`sen' = var3 * `sen'_share_2019
    gen var5_`sen' = var5 * `sen'_share_2019
    gen var6_`sen' = var6 * `sen'_share_2019
    gen var7_`sen' = var7 * `sen'_share_2019
}

*-----------------------------------------------------------------------------*
* Part 3: Run productivity regressions
*-----------------------------------------------------------------------------*

* Clear estimates
estimates clear

* Column 1: Baseline (no composition controls)
eststo baseline: ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4, ///
    absorb(firm_id#user_id yh) ///
    cluster(user_id)

* Store baseline coefficients
local base_var3 = _b[var3]
local base_var5 = _b[var5]

*-----------------------------------------------------------------------------*
* Columns 2-8: Role composition controls
*-----------------------------------------------------------------------------*

local col = 2
foreach role of local roles {
    
    * Run IV regression with role composition control
    eststo col`col': ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_`role' var5_`role' = ///
         var6 var7 var6_`role' var7_`role') ///
        var4 `role'_share_2019, ///
        absorb(firm_id#user_id yh) ///
        cluster(user_id)
    
    * Store interaction coefficients
    local b_var3_`role' = _b[var3_`role']
    local se_var3_`role' = _se[var3_`role']
    local b_var5_`role' = _b[var5_`role']
    local se_var5_`role' = _se[var5_`role']
    
    * Test joint significance of interactions
    test var3_`role' var5_`role'
    local p_joint_`role' = r(p)
    
    local col = `col' + 1
}

*-----------------------------------------------------------------------------*
* Columns 9-12: Seniority composition controls
*-----------------------------------------------------------------------------*

foreach sen of local seniority {
    
    * Run IV regression with seniority composition control
    eststo col`col': ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_`sen' var5_`sen' = ///
         var6 var7 var6_`sen' var7_`sen') ///
        var4 `sen'_share_2019, ///
        absorb(firm_id#user_id yh) ///
        cluster(user_id)
    
    * Store interaction coefficients
    local b_var3_`sen' = _b[var3_`sen']
    local se_var3_`sen' = _se[var3_`sen']
    local b_var5_`sen' = _b[var5_`sen']
    local se_var5_`sen' = _se[var5_`sen']
    
    local col = `col' + 1
}

*-----------------------------------------------------------------------------*
* Part 4: Export results tables
*-----------------------------------------------------------------------------*

* Table 1: Role composition effects
esttab baseline col2 col3 col4 col5 col6 col7 col8 ///
    using "$results/productivity_precovid_roles_full.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var4 var3_* var5_* *_share_2019) ///
    order(var3 var5 var3_* var5_* var4 *_share_2019) ///
    mtitles("Baseline" "Engineer" "Sales" "Finance" "Marketing" "Admin" "Operations" "Scientist") ///
    stats(N N_clust widstat, fmt(0 0 2) ///
          labels("Observations" "Users" "F-stat")) ///
    nonotes addnotes("Dependent variable: User productivity (total_contributions_q100)" ///
                     "All regressions include user×firm and year-half fixed effects" ///
                     "Composition measured as % of workforce in 2019 (pre-COVID)" ///
                     "Standard errors clustered by user")

* Table 2: Seniority composition effects
esttab baseline col9 col10 col11 col12 ///
    using "$results/productivity_precovid_seniority_full.tex", ///
    replace booktabs fragment ///
    b(3) se(3) star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var4 var3_level* var5_level* level*_share_2019) ///
    order(var3 var5 var3_level* var5_level* var4 level*_share_2019) ///
    mtitles("Baseline" "Entry (L1)" "Mid/Senior (L2)" "Manager (L3)" "Director+ (L4)") ///
    stats(N N_clust widstat, fmt(0 0 2) ///
          labels("Observations" "Users" "F-stat")) ///
    nonotes addnotes("Dependent variable: User productivity (total_contributions_q100)" ///
                     "All regressions include user×firm and year-half fixed effects" ///
                     "Seniority levels: L1=Entry, L2=Mid/Senior, L3=Manager, L4=Director/Executive" ///
                     "Standard errors clustered by user")

*-----------------------------------------------------------------------------*
* Part 5: Summary and interpretation
*-----------------------------------------------------------------------------*

di _n _n "="*70
di "SUMMARY: COMPOSITION EFFECTS ON REMOTE WORK PRODUCTIVITY"
di "="*70

di _n "Baseline remote work effects:"
di "  var3 coefficient: " %5.3f `base_var3'
di "  var5 coefficient: " %5.3f `base_var5'

di _n "Role Composition Interactions (var3 × role share):"
di "-"*50
foreach role of local roles {
    di "`role': " %6.4f `b_var3_`role'' " (" %6.4f `se_var3_`role'' ")" ///
       "  [p-value for joint test = " %5.3f `p_joint_`role'' "]"
}

di _n "Interpretation:"
di "Negative interaction = firms with more of this role see LESS productivity gain from remote work"
di "Positive interaction = firms with more of this role see MORE productivity gain from remote work"

*-----------------------------------------------------------------------------*
* Part 6: Heterogeneity analysis
*-----------------------------------------------------------------------------*

* Test whether effects vary by startup status
preserve
    * Merge startup indicator from firm panel
    keep companyname
    duplicates drop
    gen companyname_lower = lower(companyname)
    
    merge 1:1 companyname_lower using "$processed_data/firm_panel.dta", ///
        keepusing(startup) keep(match) nogen
    
    tempfile startup_ind
    save `startup_ind'
restore

merge m:1 companyname using `startup_ind', keep(match) nogen

* Run regression with triple interaction (example for engineers)
gen var3_eng_startup = var3 * engineer_share_2019 * startup
gen var5_eng_startup = var5 * engineer_share_2019 * startup
gen var6_eng_startup = var6 * engineer_share_2019 * startup
gen var7_eng_startup = var7 * engineer_share_2019 * startup

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_engineer var5_engineer var3_eng_startup var5_eng_startup = ///
     var6 var7 var6_engineer var7_engineer var6_eng_startup var7_eng_startup) ///
    var4 engineer_share_2019 c.engineer_share_2019#i.startup i.startup, ///
    absorb(firm_id#user_id yh) ///
    cluster(user_id)

di _n "Triple interaction (var3 × engineer % × startup): " %6.4f _b[var3_eng_startup]

*-----------------------------------------------------------------------------*
* Part 7: Graphical analysis
*-----------------------------------------------------------------------------*

* Create binned scatter plot for engineer composition effect
preserve
    * Collapse to firm level
    collapse (mean) var3 engineer_share_2019 total_contributions_q100, by(firm_id)
    
    * Create bins of engineer share
    xtile eng_bin = engineer_share_2019, nq(10)
    
    * Calculate mean productivity by bin
    collapse (mean) total_contributions_q100 engineer_share_2019, by(eng_bin)
    
    * Plot
    twoway (scatter total_contributions_q100 engineer_share_2019) ///
           (lfit total_contributions_q100 engineer_share_2019), ///
        title("Productivity by Engineer Share (2019)") ///
        ytitle("Average Productivity") ///
        xtitle("% Engineers in 2019") ///
        legend(off) ///
        name(prod_eng, replace)
        
    graph export "$results/productivity_engineer_composition.png", replace
restore

* Save results log
log using "$results/productivity_precovid_composition_log.txt", replace text
di "Full estimation results:"
estimates table col*, b(%7.4f) se(%7.4f) stats(N widstat)
log close

di _n _n "Analysis complete. Results saved to:"
di "  - $results/productivity_precovid_roles_full.tex"
di "  - $results/productivity_precovid_seniority_full.tex"
di "  - $results/productivity_engineer_composition.png"
di "  - $results/productivity_precovid_composition_log.txt"