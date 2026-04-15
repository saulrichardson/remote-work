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
* Test scaling regressions with composition changes - Working Version
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Prepare merged dataset
*-----------------------------------------------------------------------------*

* Load firm panel
use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

* Keep post-2019 data and key variables
keep if yh >= 119  // 2019 onwards
keep companyname companyname_lower yh growth_rate_we startup age rent hhi_1000 covid firm_id

* Merge composition data
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen

* Check merge success
count
di "Merged firms: " r(N)

* Keep only COVID period for main regressions
preserve
keep if covid == 1

*-----------------------------------------------------------------------------*
* Part 2: Basic scaling regression
*-----------------------------------------------------------------------------*

di _n "=== BASIC SCALING REGRESSION ==="
reg growth_rate_we startup age rent hhi_1000 i.yh, robust

* Store baseline results
est store baseline

*-----------------------------------------------------------------------------*
* Part 3: Add composition controls (main effects)
*-----------------------------------------------------------------------------*

di _n "=== SCALING WITH COMPOSITION CONTROLS ==="

* Get list of composition variables
ds pct_chg_soc*
local soc_vars `r(varlist)'

* Run regression with all SOC changes
reg growth_rate_we startup age rent hhi_1000 `soc_vars' i.yh, robust

* Store results
est store with_composition

* Test joint significance of composition variables
testparm `soc_vars'
local comp_f = r(F)
local comp_p = r(p)

di _n "Joint test of composition variables:"
di "F(" r(df) "," r(df_r) ") = " %8.2f `comp_f'
di "Prob > F = " %8.4f `comp_p'

*-----------------------------------------------------------------------------*
* Part 4: Interaction effects - Does startup scaling vary by composition?
*-----------------------------------------------------------------------------*

di _n "=== TESTING STARTUP × COMPOSITION INTERACTIONS ==="

* Create interaction terms for top 3 SOCs
local top3_socs "pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191"

foreach var of local top3_socs {
    gen startup_X_`var' = startup * `var'
}

* Run regression with interactions
reg growth_rate_we startup age rent hhi_1000 ///
    `top3_socs' ///
    startup_X_* ///
    i.yh, robust

* Test joint significance of interactions
testparm startup_X_*
di _n "Joint test of startup × composition interactions:"
di "F = " %8.2f r(F) ", p = " %8.4f r(p)

*-----------------------------------------------------------------------------*
* Part 5: Individual SOC regressions (for table columns)
*-----------------------------------------------------------------------------*

di _n "=== INDIVIDUAL SOC EFFECTS ==="

* Store results for each SOC
postfile soc_results str20 soc ///
    double b_startup se_startup p_startup ///
    double b_comp se_comp p_comp ///
    double b_int se_int p_int ///
    double r2 long nobs ///
    using "$results/scaling_soc_results.dta", replace

foreach var of local soc_vars {
    local soc = substr("`var'", 12, .)
    
    * Run regression
    quietly reg growth_rate_we startup age rent hhi_1000 ///
        `var' c.startup#c.`var' ///
        i.yh, robust
    
    * Extract coefficients
    local b_startup = _b[startup]
    local se_startup = _se[startup]
    local p_startup = 2*ttail(e(df_r), abs(`b_startup'/`se_startup'))
    
    local b_comp = _b[`var']
    local se_comp = _se[`var']
    local p_comp = 2*ttail(e(df_r), abs(`b_comp'/`se_comp'))
    
    local b_int = _b[c.startup#c.`var']
    local se_int = _se[c.startup#c.`var']
    local p_int = 2*ttail(e(df_r), abs(`b_int'/`se_int'))
    
    * Post results
    post soc_results ("`soc'") ///
        (`b_startup') (`se_startup') (`p_startup') ///
        (`b_comp') (`se_comp') (`p_comp') ///
        (`b_int') (`se_int') (`p_int') ///
        (e(r2)) (e(N))
}

postclose soc_results

* Display summary
use "$results/scaling_soc_results.dta", clear
di _n "Summary of SOC-specific results:"
list soc b_startup b_int p_int if p_int < 0.10

restore

*-----------------------------------------------------------------------------*
* Part 6: Summary statistics
*-----------------------------------------------------------------------------*

di _n "=== SUMMARY STATISTICS ==="

sum growth_rate_we startup age rent hhi_1000 pct_chg_soc* if covid == 1

* Correlation matrix
di _n "Correlations between growth and composition:"
pwcorr growth_rate_we pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191 if covid == 1, star(0.05)

di _n "Analysis complete!"