*============================================================*
* Asset 02: user_productivity_precovid_total_iv_single.tex
* Self-contained IV exporter for the active baseline table.
*
* Column-family structure:
*   - baseline_main_effect: first displayed column
*   - interacted_columns : later displayed columns with FE variants
*
* This owner also exports the exact first-stage diagnostics used by
* first_stage_summary.tex for the interacted user IV family.
*============================================================*

version 17
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname "02_user_productivity_precovid_total_iv_single"

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
! /bin/mkdir -p "`result_root'/baseline_main_effect" "`result_root'/interacted_columns" "`result_root'/first_stage"

program define asset02_baseline_main_effect_iv
    args panel_variant result_root

    use "$processed_data/user_panel_`panel_variant'.dta", clear

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

    ivreghdfe `outcome_name' (var3 = var6) var4, ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
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

program define asset02_interacted_columns_iv
    args panel_variant result_root

    capture postclose handle
    tempfile out
    postfile handle ///
        str20  model_type ///
        str20  fe_tag ///
        str40  outcome ///
        str40  param ///
        double coef se pval pre_mean ///
        double rkf nobs ///
        using `out', replace

    capture postclose handle_fs
    tempfile out_fs
    postfile handle_fs ///
        str20  fe_tag ///
        str40  outcome ///
        str8   endovar ///
        str40  param ///
        double coef se pval ///
        double partialF rkf nobs ///
        using `out_fs', replace

    foreach fe_tag in separate_fe match_fe {
        if "`fe_tag'" == "separate_fe" {
            local feopt "absorb(firm_id user_id yh)"
        }
        else {
            local feopt "absorb(firm_id#user_id yh)"
        }

        foreach outcome_name in total_contributions_q100 total_contributions_we {
            use "$processed_data/user_panel_`panel_variant'.dta", clear
            summarize `outcome_name' if covid == 0, meanonly
            local pre_mean = r(mean)

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

            if "`outcome_name'" == "total_contributions_q100" {
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
                    post handle_fs ("`fe_tag'") ("`outcome_name'") ("var3") ("`p'") ///
                        (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
                }

                estimates restore _ivreg2_var5
                local N_fs = e(N)
                foreach p in var6 var7 var4 {
                    local b    = _b[`p']
                    local se   = _se[`p']
                    local t    = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    post handle_fs ("`fe_tag'") ("`outcome_name'") ("var5") ("`p'") ///
                        (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
                }
            }
        }
    }

    postclose handle
    use `out', clear
    export delimited using "`result_root'/interacted_columns/consolidated_results.csv", replace delimiter(",") quote

    postclose handle_fs
    use `out_fs', clear
    export delimited using "`result_root'/first_stage/consolidated_results.csv", replace delimiter(",") quote
end

asset02_baseline_main_effect_iv "`panel_variant'" "`result_root'"
asset02_interacted_columns_iv "`panel_variant'" "`result_root'"

di as result "→ Wrote `result_root'/baseline_main_effect/consolidated_results.csv"
di as result "→ Wrote `result_root'/interacted_columns/consolidated_results.csv"
di as result "→ Wrote `result_root'/first_stage/consolidated_results.csv"
capture log close
