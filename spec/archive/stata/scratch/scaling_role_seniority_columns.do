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
* Scaling regressions with role and seniority composition columns
* Each column represents a different composition change measure
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Setup
*-----------------------------------------------------------------------------*

* Load firm panel
use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

* Keep COVID period only
keep if covid == 1

* Merge composition data (using simulated data for local testing)
merge m:1 companyname_lower using "$results/composition_role_seniority_simulated.dta", keep(match) nogen

* Create output file for results
capture postclose scaling_results
tempfile results_out
postfile scaling_results ///
    str40 composition_var str20 var_type ///
    double b_comp se_comp p_comp ///
    double b_startup se_startup p_startup ///
    double b_interaction se_interaction p_interaction ///
    double r2 long nobs ///
    using `results_out', replace

*-----------------------------------------------------------------------------*
* Part 1: Role-only columns (Top 10 SOCs)
*-----------------------------------------------------------------------------*

di _n "=== PANEL A: SCALING BY ROLE (TOP 10 SOCs) ==="

* Get list of role variables
ds pct_chg_soc*
local role_vars ""
foreach var of varlist pct_chg_soc* {
    if !strpos("`var'", "_") & "`var'" != "pct_chg_soc" {
        local role_vars "`role_vars' `var'"
    }
}

* Limit to top 10
local count = 0
foreach var of local role_vars {
    local count = `count' + 1
    if `count' > 10 continue, break
    
    * Run regression
    quietly reg growth_rate_we `var' startup c.startup#c.`var' age rent hhi_1000 i.yh, robust
    
    * Extract results
    local b_comp = _b[`var']
    local se_comp = _se[`var']
    local p_comp = 2*ttail(e(df_r), abs(`b_comp'/`se_comp'))
    
    local b_startup = _b[startup]
    local se_startup = _se[startup]
    local p_startup = 2*ttail(e(df_r), abs(`b_startup'/`se_startup'))
    
    local b_int = _b[c.startup#c.`var']
    local se_int = _se[c.startup#c.`var']
    local p_int = 2*ttail(e(df_r), abs(`b_int'/`se_int'))
    
    * Post results
    post scaling_results ("`var'") ("role") ///
        (`b_comp') (`se_comp') (`p_comp') ///
        (`b_startup') (`se_startup') (`p_startup') ///
        (`b_int') (`se_int') (`p_int') ///
        (e(r2)) (e(N))
    
    * Display if significant
    if `p_int' < 0.10 {
        di "`var'" ": interaction = " %9.4f `b_int' " (p=" %6.4f `p_int' ")"
    }
}

*-----------------------------------------------------------------------------*
* Part 2: Seniority-only columns
*-----------------------------------------------------------------------------*

di _n "=== PANEL B: SCALING BY SENIORITY LEVEL ==="

local seniority_vars "pct_chg_junior pct_chg_senior pct_chg_manager pct_chg_director pct_chg_vp pct_chg_exec"

foreach var of local seniority_vars {
    * Check if variable exists
    capture confirm variable `var'
    if _rc continue
    
    * Run regression
    quietly reg growth_rate_we `var' startup c.startup#c.`var' age rent hhi_1000 i.yh, robust
    
    * Extract results
    local b_comp = _b[`var']
    local se_comp = _se[`var']
    local p_comp = 2*ttail(e(df_r), abs(`b_comp'/`se_comp'))
    
    local b_startup = _b[startup]
    local se_startup = _se[startup]
    local p_startup = 2*ttail(e(df_r), abs(`b_startup'/`se_startup'))
    
    local b_int = _b[c.startup#c.`var']
    local se_int = _se[c.startup#c.`var']
    local p_int = 2*ttail(e(df_r), abs(`b_int'/`se_int'))
    
    * Post results
    post scaling_results ("`var'") ("seniority") ///
        (`b_comp') (`se_comp') (`p_comp') ///
        (`b_startup') (`se_startup') (`p_startup') ///
        (`b_int') (`se_int') (`p_int') ///
        (e(r2)) (e(N))
    
    di "`var'" ": " %7.4f `b_comp' " (" %6.4f `se_comp' ") | interaction: " %7.4f `b_int' " (p=" %5.3f `p_int' ")"
}

*-----------------------------------------------------------------------------*
* Part 3: Role × Seniority interactions (selected combinations)
*-----------------------------------------------------------------------------*

di _n "=== PANEL C: SCALING BY ROLE × SENIORITY ==="

* Test key combinations
local key_combos "pct_chg_soc131051_junior pct_chg_soc131051_senior" // Software developers
local key_combos "`key_combos' pct_chg_soc132011_junior pct_chg_soc132011_senior" // Financial managers
local key_combos "`key_combos' pct_chg_soc119111_manager pct_chg_soc119111_director" // Management

foreach var of local key_combos {
    * Check if variable exists
    capture confirm variable `var'
    if _rc continue
    
    * Run regression
    quietly reg growth_rate_we `var' startup c.startup#c.`var' age rent hhi_1000 i.yh, robust
    
    * Extract results
    local b_comp = _b[`var']
    local se_comp = _se[`var']
    local p_comp = 2*ttail(e(df_r), abs(`b_comp'/`se_comp'))
    
    local b_int = _b[c.startup#c.`var']
    local se_int = _se[c.startup#c.`var']
    local p_int = 2*ttail(e(df_r), abs(`b_int'/`se_int'))
    
    * Post results
    post scaling_results ("`var'") ("role_seniority") ///
        (`b_comp') (`se_comp') (`p_comp') ///
        (_b[startup]) (_se[startup]) (2*ttail(e(df_r), abs(_b[startup]/_se[startup]))) ///
        (`b_int') (`se_int') (`p_int') ///
        (e(r2)) (e(N))
    
    di "`var'" ": interaction = " %7.4f `b_int' " (p=" %5.3f `p_int' ")"
}

*-----------------------------------------------------------------------------*
* Part 4: Summary and export
*-----------------------------------------------------------------------------*

postclose scaling_results

* Load and summarize results
use `results_out', clear

di _n "=== SUMMARY OF SIGNIFICANT INTERACTIONS ==="
di _n "Significant startup × composition interactions (p < 0.10):"

gsort p_interaction
list composition_var var_type b_interaction p_interaction if p_interaction < 0.10, sep(0)

* Export for table creation
export excel using "$results/scaling_role_seniority_results.xlsx", ///
    sheet("raw_results") firstrow(variables) replace

* Create summary by type
di _n "Average effects by type:"
table var_type, stat(mean b_interaction) stat(count b_interaction)

* Test joint significance within each type
di _n "Joint significance tests:"
foreach type in "role" "seniority" "role_seniority" {
    preserve
    keep if var_type == "`type'"
    local n = _N
    if `n' > 0 {
        * Calculate Wald statistic
        gen wald_stat = (b_interaction / se_interaction)^2
        sum wald_stat
        local joint_stat = r(sum)
        local joint_p = chi2tail(`n', `joint_stat')
        di "`type'" ": Chi2(" `n' ") = " %8.2f `joint_stat' ", p = " %6.4f `joint_p'
    }
    restore
}

di _n "Analysis complete!"