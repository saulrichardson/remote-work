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
* Test mechanisms for why finance/management hires hurt remote productivity
* Runs on HPC with full dataset
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Build enhanced dataset with mechanism variables
*-----------------------------------------------------------------------------*

* Start with LinkedIn panel (full dataset on HPC)
use "$processed_data/stacked_linkedin_panel_full.dta", clear

* Calculate pre-COVID baselines (2019H2)
preserve
    keep if yh == 119  // 2019H2
    
    * Role shares
    gen total_emp = _N
    collapse (count) n_role=user_id, by(companyname position_role_soc)
    gen share_role = n_role / total_emp
    
    * Identify firms with existing finance/management
    gen is_finance = (position_role_soc == "13-2011")
    gen is_management = (position_role_soc == "11-9111")
    
    collapse (max) had_finance_pre=is_finance had_mgmt_pre=is_management ///
             (sum) share_finance_pre=share_role if is_finance==1 ///
                   share_mgmt_pre=share_role if is_management==1, ///
             by(companyname)
             
    tempfile pre_structure
    save `pre_structure'
restore

* Calculate hiring speed
preserve
    * Get monthly hiring rates during COVID
    keep if yh >= 120
    gen month = mofd(date)
    
    collapse (count) monthly_hires=user_id, by(companyname position_role_soc month)
    
    * Calculate coefficient of variation
    collapse (mean) avg_monthly (sd) sd_monthly, by(companyname position_role_soc)
    gen hiring_volatility = sd_monthly / avg_monthly
    
    * Flag rapid/volatile hiring
    keep if inlist(position_role_soc, "13-2011", "11-9111")
    reshape wide hiring_volatility avg_monthly, i(companyname) j(position_role_soc) string
    
    tempfile hiring_speed
    save `hiring_speed'
restore

* Geographic dispersion
preserve
    keep if yh == 123  // 2021H1
    
    * Calculate HHI of employee locations
    collapse (count) n_location=user_id, by(companyname user_location_cbsa)
    by companyname: egen total_emp = sum(n_location)
    gen share_loc = n_location / total_emp
    gen share_loc_sq = share_loc^2
    
    collapse (sum) location_hhi=share_loc_sq (count) n_locations=user_location_cbsa, by(companyname)
    gen geographic_dispersion = 1 - location_hhi
    
    tempfile dispersion
    save `dispersion'
restore

* Team structure metrics
preserve
    keep if yh == 123  // 2021H1
    
    * Average team sizes by role
    collapse (count) n_emp=user_id, by(companyname position_role_soc user_seniority)
    
    * Calculate role concentration (HHI)
    by companyname: egen total = sum(n_emp)
    gen share = n_emp / total
    gen share_sq = share^2
    
    collapse (sum) role_hhi=share_sq (count) n_roles=position_role_soc ///
             (mean) avg_team_size=n_emp, by(companyname)
             
    tempfile team_structure
    save `team_structure'
restore

*-----------------------------------------------------------------------------*
* Part 2: Create composition dataset with mechanisms
*-----------------------------------------------------------------------------*

* Follow same approach as before but add mechanism variables
keep companyname user_id date yh position_role_soc user_seniority

* Create half-year identifier
gen period = "pre" if yh < 120
replace period = "post" if yh >= 120 & yh <= 124

* Count by role
collapse (count) n_employees = user_id, ///
    by(companyname position_role_soc period)

* Get top 15 SOCs
preserve
    collapse (sum) total_n = n_employees, by(position_role_soc)
    gsort -total_n
    keep in 1/15
    keep position_role_soc
    gen keep_soc = 1
    tempfile top_socs
    save `top_socs'
restore

merge m:1 position_role_soc using `top_socs', keep(match) nogen

* Reshape to wide
reshape wide n_employees, i(companyname position_role_soc) j(period) string

* Calculate % change
gen pct_change = 100 * (n_employeespost - n_employeespre) / n_employeespre if n_employeespre > 0
replace pct_change = 100 if n_employeespre == 0 & n_employeespost > 0
replace pct_change = 0 if missing(pct_change)

* Clean SOC codes
gen soc_clean = subinstr(position_role_soc, "-", "", .)

* Reshape for regression
keep companyname soc_clean pct_change
reshape wide pct_change, i(companyname) j(soc_clean) string

* Rename variables
foreach v of varlist pct_change* {
    local newname = subinstr("`v'", "pct_change", "pct_chg_soc", .)
    rename `v' `newname'
}

* Merge mechanism variables
gen companyname_lower = lower(companyname)
merge 1:1 companyname using `pre_structure', nogen keep(match)
merge 1:1 companyname using `hiring_speed', nogen keep(match)
merge 1:1 companyname using `dispersion', nogen keep(match) 
merge 1:1 companyname using `team_structure', nogen keep(match)

save "$results/composition_mechanisms_full.dta", replace

*-----------------------------------------------------------------------------*
* Part 3: Run mechanism tests
*-----------------------------------------------------------------------------*

use "$processed_data/user_panel_precovid.dta", clear

* Merge full composition + mechanisms data
gen companyname_lower = lower(companyname)
merge m:1 companyname_lower using "$results/composition_mechanisms_full.dta", keep(match) nogen

* Create mechanism interactions
local finance_soc "pct_chg_soc132011"  // Financial managers

* Test 1: Coordination costs (geographic dispersion)
gen var3_comp = var3 * `finance_soc'
gen var5_comp = var5 * `finance_soc'
gen var3_comp_disp = var3 * `finance_soc' * geographic_dispersion
gen var5_comp_disp = var5 * `finance_soc' * geographic_dispersion

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_comp var5_comp var3_comp_disp var5_comp_disp = ///
     var6 var7 var6_comp var7_comp var6_comp_disp var7_comp_disp) ///
    var4 `finance_soc' geographic_dispersion c.`finance_soc'#c.geographic_dispersion ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== MECHANISM 1: COORDINATION COSTS ==="
di "Base composition effect: " %9.3f _b[var3_comp]
di "Dispersion interaction: " %9.3f _b[var3_comp_disp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp_disp]/_se[var3_comp_disp])) ")"

* Test 2: Cultural mismatch (prior experience)
gen var3_comp_exp = var3 * `finance_soc' * had_finance_pre
gen var5_comp_exp = var5 * `finance_soc' * had_finance_pre

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_comp var5_comp var3_comp_exp var5_comp_exp = ///
     var6 var7 var6_comp var7_comp var6_comp_exp var7_comp_exp) ///
    var4 `finance_soc' had_finance_pre c.`finance_soc'#c.had_finance_pre ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== MECHANISM 2: CULTURAL MISMATCH ==="
di "Base composition effect: " %9.3f _b[var3_comp] 
di "Prior experience interaction: " %9.3f _b[var3_comp_exp] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp_exp]/_se[var3_comp_exp])) ")"

* Test 3: Hiring quality (volatility)
gen var3_comp_vol = var3 * `finance_soc' * hiring_volatility132011
gen var5_comp_vol = var5 * `finance_soc' * hiring_volatility132011

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_comp var5_comp var3_comp_vol var5_comp_vol = ///
     var6 var7 var6_comp var7_comp var6_comp_vol var7_comp_vol) ///
    var4 `finance_soc' hiring_volatility132011 c.`finance_soc'#c.hiring_volatility132011 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== MECHANISM 3: HIRING QUALITY ==="
di "Base composition effect: " %9.3f _b[var3_comp]
di "Hiring volatility interaction: " %9.3f _b[var3_comp_vol] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp_vol]/_se[var3_comp_vol])) ")"

* Test 4: Team structure (role concentration)
gen var3_comp_hhi = var3 * `finance_soc' * role_hhi
gen var5_comp_hhi = var5 * `finance_soc' * role_hhi

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_comp var5_comp var3_comp_hhi var5_comp_hhi = ///
     var6 var7 var6_comp var7_comp var6_comp_hhi var7_comp_hhi) ///
    var4 `finance_soc' role_hhi c.`finance_soc'#c.role_hhi ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "=== MECHANISM 4: TEAM STRUCTURE ==="  
di "Base composition effect: " %9.3f _b[var3_comp]
di "Role concentration interaction: " %9.3f _b[var3_comp_hhi] " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp_hhi]/_se[var3_comp_hhi])) ")"

di _n "Analysis complete!"