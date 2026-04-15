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
* Composition analysis using existing firm-level data
* Works with data available locally (no individual LinkedIn needed)
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Create role composition from firm SOC panel
*-----------------------------------------------------------------------------*

* Use the composition data we created with Python
capture confirm file "$results/composition_role_only.dta"
if _rc == 0 {
    di "Using Python-generated composition data..."
    use "$results/composition_role_only.dta", clear
    
    * Check what we have
    ds pct_chg_soc*
    local n_vars : word count `r(varlist)'
    di "Found `n_vars' SOC composition variables"
    
    * Save for merging
    tempfile comp_data
    save `comp_data'
}
else {
    di "Using existing composition sample data..."
    use "$results/composition_sample.dta", clear
    tempfile comp_data
    save `comp_data'
}

*-----------------------------------------------------------------------------*
* Part 2: Run scaling regression with available composition
*-----------------------------------------------------------------------------*

di _n "=== SCALING REGRESSION WITH ROLE COMPOSITION ==="

* Merge with firm panel
use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)
keep if covid == 1

* Merge composition data
merge m:1 companyname_lower using `comp_data', keep(match) nogen

* Get list of composition variables
ds pct_chg_soc*
local comp_vars `r(varlist)'

* Display available variables
di _n "Available composition variables:"
foreach v of local comp_vars {
    qui sum `v'
    if r(N) > 100 {
        di "  `v': N=" r(N) ", mean=" %6.1f r(mean)
    }
}

* Run main regression with all composition variables
reg growth_rate_we startup age rent hhi_1000 `comp_vars' i.yh, robust

* Test joint significance
testparm `comp_vars'
di _n "Joint test of composition variables: F=" %6.2f r(F) ", p=" %6.4f r(p)

* Individual interactions with startup
di _n "Testing startup interactions for key roles:"

local key_roles ""
foreach v of local comp_vars {
    if strpos("`v'", "1511") | strpos("`v'", "1320") | strpos("`v'", "1191") {
        local key_roles "`key_roles' `v'"
    }
}

foreach v of local key_roles {
    quietly reg growth_rate_we startup age rent hhi_1000 ///
        `v' c.startup#c.`v' ///
        i.yh, robust
        
    local b_int = _b[c.startup#c.`v']
    local se_int = _se[c.startup#c.`v']
    local p_int = 2*ttail(e(df_r), abs(`b_int'/`se_int'))
    
    if `p_int' < 0.10 {
        di "`v'" ": interaction = " %7.4f `b_int' " (p=" %6.4f `p_int' ")"
    }
}

*-----------------------------------------------------------------------------*
* Part 3: Productivity regression with composition controls
*-----------------------------------------------------------------------------*

di _n "=== PRODUCTIVITY REGRESSION WITH COMPOSITION CONTROLS ==="

use "$processed_data/user_panel_precovid.dta", clear
gen companyname_lower = lower(companyname)

* Merge composition
merge m:1 companyname_lower using `comp_data', keep(match) nogen

* Focus on one key composition variable
local key_comp "pct_chg_soc132011"  // Financial managers
capture confirm variable `key_comp'
if _rc == 0 {
    * Create interactions
    gen var3_comp = var3 * `key_comp'
    gen var5_comp = var5 * `key_comp'
    gen var6_comp = var6 * `key_comp'
    gen var7_comp = var7 * `key_comp'
    
    * Run IV regression
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
        var4 `key_comp' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    di _n "Composition interaction effects:"
    di "Remote × Post × Finance Managers %∆: " %9.3f _b[var3_comp] ///
       " (p=" %6.4f 2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp])) ")"
}
else {
    di "Key composition variable not found"
}

di _n "Analysis complete!"