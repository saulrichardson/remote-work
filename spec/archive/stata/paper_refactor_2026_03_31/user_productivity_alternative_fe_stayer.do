*============================================================*
*  user_productivity_alternative_fe_stayer.do
*  — Alternative FE variants on the boundary-stayer sample.
*    Mirrors user_productivity_alternative_fe.do but filters
*    to stayer_boundary & spell spanning the boundary.
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname user_productivity_alternative_fe_`panel_variant'_stayer

// 0) Setup environment
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
log using "$LOG_DIR/`specname'.log", replace text

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// Outcomes needed for Table 2/3 style columns
local outcomes total_contributions_q100 ///
                total_contributions_we

local out "`result_dir'/main_tmp.dta"
capture postclose handle
postfile handle ///
    str20   model_type          ///
    str20   fe_tag              ///
    str40  outcome             ///
    str40  param               ///
    double coef se pval pre_mean ///
    double rkf nobs            ///
    using "`out'", replace

local out_fs "`result_dir'/fs_tmp.dta"
capture postclose handle_fs
postfile handle_fs ///
    str20   fe_tag              ///
    str40  outcome             ///
    str20   endovar             ///
    str40  param               ///
    double coef se pval        ///
    double partialF rkf nobs   ///
    using "`out_fs'", replace

// Helper program: restrict to boundary stayers once per loop
program define __keep_stayers
    sort user_id y half
    by user_id: egen pre_yh_max  = max(cond(covid==0, yh, .))
    by user_id: egen post_yh_min = min(cond(covid==1, yh, .))

    gen firm_pre_last   = firm_id if yh==pre_yh_max  & covid==0
    gen firm_post_first = firm_id if yh==post_yh_min & covid==1
    by user_id: egen firm_pre_last_u   = max(firm_pre_last)
    by user_id: egen firm_post_first_u = max(firm_post_first)

    by user_id (y half): gen byte firm_change = firm_id != firm_id[_n-1] if _n>1
    replace firm_change = 0 if missing(firm_change)
    by user_id: gen spell_id = sum(firm_change) + 1

    gen mark_pre  = yh==pre_yh_max  & covid==0
    gen mark_post = yh==post_yh_min & covid==1
    by user_id: egen spell_pre  = max(cond(mark_pre,  spell_id, .))
    by user_id: egen spell_post = max(cond(mark_post, spell_id, .))

    gen byte stayer_boundary = firm_pre_last_u==firm_post_first_u ///
        & firm_pre_last_u<. & firm_post_first_u<. ///
        & spell_pre==spell_post & spell_pre<.

    keep if stayer_boundary & spell_id==spell_pre
    drop _merge
end

//-------------------------------------------------------------
// FE spec: firm + user + yh  (tag = fyhu)
//-------------------------------------------------------------
local feopt "absorb(firm_id user_id yh)"
local tag   "fyhu"

foreach y of local outcomes {
    use "$processed_data/user_panel_`panel_variant'.dta", clear
    __keep_stayers

    display as text ">> FE spec: (tag=`tag')" 
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
    reghdfe `y' var3 var5 var4, `feopt' vce(cluster user_id)
    local N = e(N)  

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean') ///
                        (.) (`N')
    }

    // IV
    ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    local rkf = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean') ///
                        (`rkf') (`N')
    }

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
        post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
                        (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
    }

    estimates restore _ivreg2_var5
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
                        (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
    }
}

//-------------------------------------------------------------
// FE spec: firm×user match + yh (tag = firmbyuseryh)
//-------------------------------------------------------------
local feopt "absorb(firm_id#user_id yh)"
local tag   "firmbyuseryh"

foreach y of local outcomes {
    use "$processed_data/user_panel_`panel_variant'.dta", clear
    __keep_stayers

    display as text ">> FE spec: (tag=`tag')" 
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
    reghdfe `y' var3 var5 var4, `feopt' vce(cluster user_id)
    local N = e(N)  

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean') ///
                        (.) (`N')
    }

    // IV
    ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    local rkf = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean') ///
                        (`rkf') (`N')
    }

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
        post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
                        (`b') (`se') (`pval') ///
                        (`F3') (`rkf') (`N_fs')
    }

    estimates restore _ivreg2_var5
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
                        (`b') (`se') (`pval') ///
                        (`F5') (`rkf') (`N_fs')
    }
}

// Export
postclose handle
use "`out'", clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use "`out_fs'", clear
export delimited using "`result_dir'/first_stage.csv", ///
        replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
capture log close
