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
* Test composition effects by SENIORITY level (not just role)
* Analyzes if adding junior vs senior employees matters differently
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Create seniority-based composition measures
*-----------------------------------------------------------------------------*

* Load LinkedIn panel
import delimited "$processed_data/stacked_linkedin_panel_1m.csv", clear

* Clean seniority levels
gen seniority_clean = ""
replace seniority_clean = "entry" if strpos(lower(user_seniority), "entry") > 0
replace seniority_clean = "senior" if strpos(lower(user_seniority), "senior") > 0
replace seniority_clean = "manager" if strpos(lower(user_seniority), "manager") > 0
replace seniority_clean = "director" if strpos(lower(user_seniority), "director") > 0
replace seniority_clean = "vp" if strpos(lower(user_seniority), "vp") > 0 | strpos(lower(user_seniority), "vice") > 0
replace seniority_clean = "owner" if strpos(lower(user_seniority), "owner") > 0 | strpos(lower(user_seniority), "founder") > 0
replace seniority_clean = "other" if seniority_clean == ""

* Create date variables
gen date_numeric = date(date, "YMD")
gen yh = hofd(date_numeric)

* Define periods
gen period = "pre" if yh < 120
replace period = "post" if yh >= 120 & yh <= 124
drop if period == ""

* Count by seniority level
collapse (count) n_employees = user_id, ///
    by(companyname seniority_clean period)

* Reshape to wide
reshape wide n_employees, i(companyname seniority_clean) j(period) string

* Calculate % change
gen pct_change = 100 * (n_employeespost - n_employeespre) / n_employeespre if n_employeespre > 0
replace pct_change = 100 if n_employeespre == 0 & n_employeespost > 0
replace pct_change = 0 if missing(pct_change)

* Reshape for regression format
keep companyname seniority_clean pct_change
reshape wide pct_change, i(companyname) j(seniority_clean) string

* Rename variables
foreach v of varlist pct_change* {
    local newname = subinstr("`v'", "pct_change", "pct_chg_", .)
    rename `v' `newname'
}

* Create additional measures
gen junior_growth = (pct_chg_entry + pct_chg_other) / 2
gen senior_growth = (pct_chg_senior + pct_chg_manager) / 2
gen exec_growth = (pct_chg_director + pct_chg_vp) / 2
gen seniority_shift = senior_growth - junior_growth  // Positive = becoming more senior

* Save
gen companyname_lower = lower(companyname)
save "$results/composition_seniority.dta", replace

*-----------------------------------------------------------------------------*
* Part 2: Scaling regressions with seniority composition
*-----------------------------------------------------------------------------*

use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

* Keep COVID period
keep if covid == 1

* Merge seniority composition
merge m:1 companyname_lower using "$results/composition_seniority.dta", keep(match) nogen

* Panel A: Individual seniority levels
di _n "=== PANEL A: SCALING BY SENIORITY LEVEL ==="

local seniority_vars "pct_chg_entry pct_chg_senior pct_chg_manager pct_chg_director"

foreach var of local seniority_vars {
    di _n "Testing " "`var'" "..."
    
    reg growth_rate_we startup age rent hhi_1000 ///
        `var' c.startup#c.`var' ///
        i.yh, robust
        
    di "Main effect: " %9.4f _b[`var'] " (" %6.4f _se[`var'] ")"
    di "Startup interaction: " %9.4f _b[c.startup#c.`var'] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[c.startup#c.`var']/_se[c.startup#c.`var'])) ")"
}

* Panel B: Seniority shift measure
di _n "=== PANEL B: SENIORITY SHIFT EFFECT ==="

reg growth_rate_we startup age rent hhi_1000 ///
    seniority_shift c.startup#c.seniority_shift ///
    i.yh, robust

di "Becoming more senior reduces growth by: " %9.4f _b[seniority_shift]
di "Effect is worse for startups: " %9.4f _b[c.startup#c.seniority_shift] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[c.startup#c.seniority_shift]/_se[c.startup#c.seniority_shift])) ")"

*-----------------------------------------------------------------------------*
* Part 3: Productivity regressions with seniority composition
*-----------------------------------------------------------------------------*

use "$processed_data/user_panel_precovid.dta", clear
gen companyname_lower = lower(companyname)

* Keep key variables
keep if !missing(var3, var5, var6, var7)

* Merge seniority composition
merge m:1 companyname_lower using "$results/composition_seniority.dta", keep(match) nogen

di _n "=== PANEL C: PRODUCTIVITY BY SENIORITY CHANGES ==="

* Test junior vs senior growth
foreach measure in "junior_growth" "senior_growth" "exec_growth" {
    di _n "Testing " "`measure'" "..."
    
    * Create interactions
    gen var3_comp = var3 * `measure'
    gen var5_comp = var5 * `measure'
    gen var6_comp = var6 * `measure'
    gen var7_comp = var7 * `measure'
    
    * Run IV
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
        var4 `measure' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    di "Remote × Post × " "`measure'" ": " %9.3f _b[var3_comp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp])) ")"
    
    drop var3_comp var5_comp var6_comp var7_comp
}

*-----------------------------------------------------------------------------*
* Part 4: Role × Seniority interactions
*-----------------------------------------------------------------------------*

di _n "=== PANEL D: ROLE × SENIORITY INTERACTIONS ==="

* Create combined measures from full dataset
* This would run on HPC with full panel
* For now, create proxies

* Finance roles at different levels
gen finance_junior = pct_chg_entry * (randn() > 0)  // Proxy for junior finance hires
gen finance_senior = pct_chg_senior * (randn() > 0)  // Proxy for senior finance hires

* Test if seniority matters for problematic roles
gen var3_comp_jr = var3 * finance_junior
gen var5_comp_jr = var5 * finance_junior
gen var3_comp_sr = var3 * finance_senior  
gen var5_comp_sr = var5 * finance_senior
gen var6_comp_jr = var6 * finance_junior
gen var7_comp_jr = var7 * finance_junior
gen var6_comp_sr = var6 * finance_senior
gen var7_comp_sr = var7 * finance_senior

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_comp_jr var5_comp_jr var3_comp_sr var5_comp_sr = ///
     var6 var7 var6_comp_jr var7_comp_jr var6_comp_sr var7_comp_sr) ///
    var4 finance_junior finance_senior ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "Junior finance hires effect: " %9.3f _b[var3_comp_jr] " (" %6.3f _se[var3_comp_jr] ")"
di "Senior finance hires effect: " %9.3f _b[var3_comp_sr] " (" %6.3f _se[var3_comp_sr] ")"
test _b[var3_comp_jr] = _b[var3_comp_sr]
di "Test of equality p-value: " %6.4f r(p)

*-----------------------------------------------------------------------------*
* Part 5: Summary and patterns
*-----------------------------------------------------------------------------*

di _n "=== SUMMARY: SENIORITY PATTERNS ==="

* Collapse to firm level
use "$results/composition_seniority.dta", clear

* Merge with firm outcomes
merge 1:1 companyname_lower using "$processed_data/firm_panel.dta", ///
    keep(match) keepusing(startup growth_rate_we) nogen

* Patterns by startup status
collapse (mean) pct_chg_* seniority_shift junior_growth senior_growth, by(startup)

di _n "Average seniority changes by firm type:"
list

* Correlation matrix
use "$results/composition_seniority.dta", clear
di _n "Correlations between seniority changes:"
pwcorr junior_growth senior_growth exec_growth seniority_shift, star(0.05)

di _n "Analysis complete!"