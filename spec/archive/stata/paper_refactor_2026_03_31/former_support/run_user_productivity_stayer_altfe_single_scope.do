*============================================================*
* Narrow support helper for the alternative-FE boundary-stayer
* single-scope user productivity asset.
*============================================================*

args panel_variant specname result_subdir model_mode
if "`panel_variant'" == "" local panel_variant "precovid"
if "`specname'" == "" local specname "user_productivity_stayer_altfe_single_scope"
if "`result_subdir'" == "" {
    di as error "run_user_productivity_stayer_altfe_single_scope.do requires result_subdir"
    exit 198
}
if "`model_mode'" == "" local model_mode "both"

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

local result_dir "$results/`result_subdir'"
! /bin/mkdir -p "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str20   model_type ///
    str20   fe_tag ///
    str40   outcome ///
    str40   param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local outcomes total_contributions_q100 total_contributions_we

program define __keep_stayers_asset
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

foreach fe_tag in fyhu firmbyuseryh {
    if "`fe_tag'" == "fyhu" {
        local feopt "absorb(firm_id user_id yh)"
    }
    else {
        local feopt "absorb(firm_id#user_id yh)"
    }

    foreach outcome_name of local outcomes {
        use "$processed_data/user_panel_`panel_variant'.dta", clear
        __keep_stayers_asset
        summarize `outcome_name' if covid == 0, meanonly
        local pre_mean = r(mean)

        if inlist("`model_mode'", "ols", "both") {
            reghdfe `outcome_name' var3 var5 var4, `feopt' vce(cluster user_id)
            local N = e(N)
            foreach p in var3 var5 var4 {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("OLS") ("`fe_tag'") ("`outcome_name'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`N')
            }
        }

        if inlist("`model_mode'", "iv", "both") {
            ivreghdfe ///
                `outcome_name' (var3 var5 = var6 var7) var4, ///
                `feopt' vce(cluster user_id) savefirst
            local rkf = e(rkf)
            local N = e(N)
            foreach p in var3 var5 var4 {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`fe_tag'") ("`outcome_name'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N')
            }
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
capture log close
