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
* Scaling regressions with composition changes
* Each column shows scaling effects for different roles/seniority
*=============================================================================*

clear all
set more off

do "src/globals.do"

* Load firm panel with composition changes
use "$processed_data/firm_panel_with_composition.dta", clear

* Keep only necessary variables and observations
keep if !missing(growth_rate_we)
keep if inrange(yh, yh(2019,1), yh(2021,2))

*-----------------------------------------------------------------------------*
* Scaling regression by SOC (role) composition changes
*-----------------------------------------------------------------------------*

* Store results
postfile results str32 specification str32 soc_code ///
    double coef double se double pval double r2 long nobs ///
    using "$results/scaling_by_soc_results.dta", replace

* Baseline model (no composition controls)
reg growth_rate_we startup age rent hhi_1000 i.yh if covid == 1
post results ("baseline") ("all") (_b[startup]) (_se[startup]) ///
    (2*ttail(e(df_r), abs(_b[startup]/_se[startup]))) (e(r2)) (e(N))

* Loop through top SOCs
foreach v of varlist pct_chg_soc* {
    local soc = substr("`v'", 13, .)  // Extract SOC code from variable name
    
    * Check if variable has variation
    quietly sum `v'
    if r(sd) > 0 {
        * Regression with SOC-specific scaling
        reg growth_rate_we startup age rent hhi_1000 `v' c.startup#c.`v' i.yh if covid == 1
        
        * Store main effect and interaction
        local b_main = _b[startup]
        local se_main = _se[startup]
        local p_main = 2*ttail(e(df_r), abs(`b_main'/`se_main'))
        
        * Check if interaction exists
        capture local b_int = _b[c.startup#c.`v']
        if _rc == 0 {
            post results ("main_effect") ("`soc'") (`b_main') (`se_main') (`p_main') (e(r2)) (e(N))
            post results ("interaction") ("`soc'") (`b_int') (_se[c.startup#c.`v']) ///
                (2*ttail(e(df_r), abs(`b_int'/_se[c.startup#c.`v']))) (e(r2)) (e(N))
        }
    }
}

postclose results

* Create formatted table
use "$results/scaling_by_soc_results.dta", clear
export delimited "$results/scaling_by_soc_results.csv", replace

*-----------------------------------------------------------------------------*
* Scaling regression by seniority changes
*-----------------------------------------------------------------------------*

use "$processed_data/firm_panel_with_composition.dta", clear
keep if !missing(growth_rate_we) & covid == 1

* Simple regression with seniority concentration change
reg growth_rate_we startup age rent hhi_1000 sen_concentration_chg ///
    c.startup#c.sen_concentration_chg i.yh

* Display results
di _n "=== Scaling by Seniority Concentration Change ==="
di "Startup main effect: " %9.3f _b[startup] " (" %6.3f _se[startup] ")"
di "Seniority change effect: " %9.3f _b[sen_concentration_chg] " (" %6.3f _se[sen_concentration_chg] ")"
di "Startup × Seniority interaction: " %9.3f _b[c.startup#c.sen_concentration_chg] ///
    " (" %6.3f _se[c.startup#c.sen_concentration_chg] ")"

* Export results
outreg2 using "$results/scaling_seniority_results.doc", replace ///
    title("Scaling Effects by Seniority Composition Change") ///
    ctitle("Growth Rate") ///
    addtext(Year-Half FE, Yes) ///
    dec(3)

di "Scaling composition regressions completed"