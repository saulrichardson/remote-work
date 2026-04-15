*============================================================*
* Asset 11: first_stage_summary.tex
* Self-contained first-stage summary exporter.
*============================================================*

version 17
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/11_first_stage_summary.log", replace text

local specname "11_first_stage_summary"
local result_root "$results/`specname'"
! /bin/mkdir -p "`result_root'/user_standard" "`result_root'/user_altfe" "`result_root'/firm_scaling"

* user baseline first stage
use "$processed_data/user_panel_`panel_variant'.dta", clear
tempfile out_user
capture postclose handle_user
postfile handle_user ///
    str8 endovar ///
    str40 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_user', replace
local outcome_name total_contributions_q100
ivreghdfe `outcome_name' (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) cluster(user_id) savefirst
local rkf = e(rkf)
matrix FS = e(first)
local F3 = FS[4,1]
local F5 = FS[4,2]
estimates restore _ivreg2_var3
local N_fs = e(N)
foreach p in var6 var7 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_user ("var3") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
}
estimates restore _ivreg2_var5
local N_fs = e(N)
foreach p in var6 var7 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_user ("var5") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
}
postclose handle_user
use `out_user', clear
export delimited using "`result_root'/user_standard/first_stage.csv", replace delimiter(",") quote

* user alternative FE first stage (firmbyuseryh only)
use "$processed_data/user_panel_`panel_variant'.dta", clear
tempfile out_alt
capture postclose handle_alt
postfile handle_alt ///
    str20 fe_tag ///
    str40 outcome ///
    str20 endovar ///
    str40 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_alt', replace
local feopt "absorb(firm_id#user_id yh)"
ivreghdfe ///
    total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    `feopt' vce(cluster user_id) savefirst
local rkf = e(rkf)
matrix FS = e(first)
local F3 = FS[4,1]
local F5 = FS[4,2]
estimates restore _ivreg2_var3
local N_fs = e(N)
foreach p in var6 var7 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_alt ("firmbyuseryh") ("total_contributions_q100") ("var3") ("`p'") ///
        (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
}
estimates restore _ivreg2_var5
local N_fs = e(N)
foreach p in var6 var7 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_alt ("firmbyuseryh") ("total_contributions_q100") ("var5") ("`p'") ///
        (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
}
postclose handle_alt
use `out_alt', clear
export delimited using "`result_root'/user_altfe/first_stage_fstats.csv", replace delimiter(",") quote

* firm first stage
use "$processed_data/firm_panel.dta", clear
tempfile out_firm
capture postclose handle_firm
postfile handle_firm ///
    str8 endovar ///
    str40 param ///
    double coef se pval ///
    double partialF rkf nobs ///
    using `out_firm', replace
ivreghdfe growth_rate_we (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id) savefirst
local rkf = e(rkf)
matrix FS = e(first)
local F3 = FS[4,1]
local F5 = FS[4,2]
estimates restore _ivreg2_var3
local N_fs = e(N)
foreach p in var6 var7 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_firm ("var3") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
}
estimates restore _ivreg2_var5
local N_fs = e(N)
foreach p in var6 var7 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_firm ("var5") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
}
postclose handle_firm
use `out_firm', clear
export delimited using "`result_root'/firm_scaling/first_stage.csv", replace delimiter(",") quote

di as result "→ Wrote `result_root'/user_standard/first_stage.csv"
di as result "→ Wrote `result_root'/user_altfe/first_stage_fstats.csv"
di as result "→ Wrote `result_root'/firm_scaling/first_stage.csv"
capture log close
