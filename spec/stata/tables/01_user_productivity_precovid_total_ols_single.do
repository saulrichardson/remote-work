*============================================================*
* Asset 01: user_productivity_precovid_total_ols_single.tex
* Self-contained OLS exporter for the active baseline table.
*
* Column-family structure:
*   - baseline_main_effect: first displayed column
*   - interacted_columns : later displayed columns with FE variants
*============================================================*

version 17
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname "01_user_productivity_precovid_total_ols_single"

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

program define asset01_baseline_main_effect_ols
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

    postclose handle
    use `out', clear
    export delimited using "`result_root'/baseline_main_effect/consolidated_results.csv", replace delimiter(",") quote
end

program define asset01_interacted_columns_ols
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
    }

    postclose handle
    use `out', clear
    export delimited using "`result_root'/interacted_columns/consolidated_results.csv", replace delimiter(",") quote
end

asset01_baseline_main_effect_ols "`panel_variant'" "`result_root'"
asset01_interacted_columns_ols "`panel_variant'" "`result_root'"

di as result "→ Wrote `result_root'/baseline_main_effect/consolidated_results.csv"
di as result "→ Wrote `result_root'/interacted_columns/consolidated_results.csv"
capture log close
