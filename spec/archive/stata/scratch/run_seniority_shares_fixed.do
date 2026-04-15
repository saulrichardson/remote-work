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
* Run fixed seniority shares analysis 
*============================================================*

clear all
set more off

// Globals
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global results "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

local specname "user_productivity_composition"
local result_dir "$results/`specname'"

// Load and prepare data
use "$processed_data/user_panel_precovid.dta", clear
tempfile user_data
save `user_data'

// Prepare seniority share data
import delimited "$processed_data/seniority_scaling_growth.csv", clear
gen yh = yh(year, half)
gen sen_label = "sen" + string(seniority_level)
keep companyname yh sen_label seniority_share
reshape wide seniority_share, i(companyname yh) j(sen_label) string
rename seniority_share* share_*
tempfile seniority_share_wide
save `seniority_share_wide'

// CORRECTED Part B2: Seniority Composition Controls (Shares)
use `user_data', clear
capture drop _merge
merge m:1 companyname yh using `seniority_share_wide'
keep if _merge == 1 | _merge == 3
drop _merge

// FIXED zero-fill logic for seniority
capture unab svars: share_sen*
if _rc == 0 {
    foreach v of local svars {
        quietly replace `v' = 0 if missing(`v')
    }
}

// Set up results collection
capture postclose handle_sen_sh
tempfile out_sen_sh
postfile handle_sen_sh str20 seniority str8 model_type str40 param double coef se pval pre_mean nobs rkf using `out_sen_sh', replace

// Baseline
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)
reghdfe total_contributions_q100 var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_sen_sh ("Baseline") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
}
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 {
    local b = _b[`p']
    local se = _se[`p']
    local pval = 2*ttail(e(df_r), abs(`b'/`se'))
    post handle_sen_sh ("Baseline") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
}

// Seniority-specific regressions
forvalues sen = 1/4 {
    capture confirm variable share_sen`sen'
    if _rc == 0 {
        gen sen`sen'_share_covid = covid * share_sen`sen'
        gen sen`sen'_share_inter = covid * share_sen`sen' * startup

        count if !missing(share_sen`sen') & !missing(total_contributions_q100)
        summarize total_contributions_q100 if covid == 0, meanonly
        local pre_mean = r(mean)

        // OLS
        reghdfe total_contributions_q100 var3 var5 var4 sen`sen'_share_covid sen`sen'_share_inter, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        local N = e(N)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_sen_sh ("Level_`sen'") ("OLS") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (.)
        }
        local b = _b[sen`sen'_share_inter]
        local se = _se[sen`sen'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_sen_sh ("Level_`sen'") ("OLS") ("sen`sen'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (.)

        // IV
        ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 sen`sen'_share_covid sen`sen'_share_inter, absorb(firm_id#user_id yh) vce(cluster user_id) keepsingletons
        local N = e(N)
        local rkf = e(rkf)
        foreach p in var3 var5 {
            local b = _b[`p']
            local se = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle_sen_sh ("Level_`sen'") ("IV") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')
        }
        local b = _b[sen`sen'_share_inter]
        local se = _se[sen`sen'_share_inter]
        local pval = 2*ttail(e(df_r), abs(`b'/`se'))
        post handle_sen_sh ("Level_`sen'") ("IV") ("sen`sen'_interaction") (`b') (`se') (`pval') (`pre_mean') (`N') (`rkf')

        drop sen`sen'_share_covid sen`sen'_share_inter
    }
}

// Save results
postclose handle_sen_sh
use `out_sen_sh', clear
export delimited using "`result_dir'/seniority_composition_share_results_fixed.csv", replace
save "`result_dir'/seniority_composition_share_results_fixed.dta", replace

display "Fixed seniority share results saved!"