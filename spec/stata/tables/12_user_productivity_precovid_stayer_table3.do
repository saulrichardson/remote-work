*============================================================*
* Asset 12: user_productivity_precovid_stayer_table3.tex
* Self-contained OLS + IV exporter for the boundary-stayer table.
*
* Column-family structure:
*   - baseline_main_effect: first displayed column
*   - interacted_columns : later displayed columns under separate FE
*============================================================*

version 17
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname "12_user_productivity_precovid_stayer_table3"

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

local result_root "$results/`specname'"
! /bin/mkdir -p "`result_root'/baseline_main_effect" "`result_root'/interacted_columns"

program define asset12_keep_stayers
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
    capture drop _merge
end

program define a12_base
    args panel_variant result_root

    use "$processed_data/user_panel_`panel_variant'.dta", clear
    asset12_keep_stayers

    capture postclose handle
    tempfile out
    postfile handle ///
        str8   model_type ///
        str40  outcome ///
        str40  param ///
        double coef se pval pre_mean ///
        double rkf nobs ///
        using `out', replace

    local outcome_name total_contributions_q100
    summarize `outcome_name' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `outcome_name' var3 var4, absorb(user_id firm_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe `outcome_name' (var3 = var6) var4, ///
        absorb(user_id firm_id yh) vce(cluster user_id)
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    postclose handle
    use `out', clear
    export delimited using "`result_root'/baseline_main_effect/consolidated_results.csv", replace delimiter(",") quote
end

program define a12_interacted
    args panel_variant result_root

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

    local fe_tag "separate_fe"
    local feopt "absorb(firm_id user_id yh)"

    foreach outcome_name in total_contributions_q100 total_contributions_we {
        use "$processed_data/user_panel_`panel_variant'.dta", clear
        asset12_keep_stayers
        summarize `outcome_name' if covid == 0, meanonly
        local pre_mean = r(mean)

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

        ivreghdfe ///
            `outcome_name' (var3 var5 = var6 var7) var4, ///
            `feopt' vce(cluster user_id)
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

    postclose handle
    use `out', clear
    export delimited using "`result_root'/interacted_columns/consolidated_results.csv", replace delimiter(",") quote
end

a12_base "`panel_variant'" "`result_root'"
a12_interacted "`panel_variant'" "`result_root'"

di as result "→ Wrote `result_root'/baseline_main_effect/consolidated_results.csv"
di as result "→ Wrote `result_root'/interacted_columns/consolidated_results.csv"
capture log close
