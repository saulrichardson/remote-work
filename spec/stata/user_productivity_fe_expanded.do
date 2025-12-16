*============================================================*
* user_productivity_fe_expanded.do
* Exports OLS + IV results for user productivity with expanded
* fixed-effect variants (standalone; does not modify the main
* workflow or outputs).
*============================================================*

//---------------------------------------------------------------------------
// 0) Parse variant argument before bootstrapping paths
//---------------------------------------------------------------------------
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname user_productivity_fe_expanded_`panel_variant'

//---------------------------------------------------------------------------
// 1) Bootstrap paths and logging
//---------------------------------------------------------------------------
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

//---------------------------------------------------------------------------
// 2) Globals for reuse inside the helper program
//---------------------------------------------------------------------------
global PANEL_VARIANT "`panel_variant'"
global RESULT_DIR "$results/`specname'"
global OUTCOMES "total_contributions_q100 restricted_contributions_q100 total_contributions_we restricted_contributions_we"

cap mkdir "$RESULT_DIR"

//---------------------------------------------------------------------------
// 3) Postfiles
//---------------------------------------------------------------------------
capture postclose handle
tempfile out
postfile handle ///
    str20   model_type ///
    str20   fe_tag ///
    str40   outcome ///
    str40   param ///
    double  coef se pval pre_mean ///
    double  rkf nobs ///
    using `out', replace

capture postclose handle_fs
tempfile out_fs
postfile handle_fs ///
    str20   fe_tag ///
    str40   outcome ///
    str20   endovar ///
    str40   param ///
    double  coef se pval ///
    double  partialF rkf nobs ///
    using `out_fs', replace

//---------------------------------------------------------------------------
// 4) Helper: run one FE variant across all outcomes
//---------------------------------------------------------------------------
program define run_fe
    args tag feopt need_year need_industry

    foreach y of global OUTCOMES {
        use "$processed_data/user_panel_$PANEL_VARIANT.dta", clear

        if "`need_year'" == "yes" {
            cap confirm variable year
            if _rc gen int year = year(dofh(yh))
        }
        if "`need_industry'" == "yes" {
            cap confirm variable industry_id
            if _rc {
                di as error "industry_id missing for tag `tag'."
                exit 198
            }
        }

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

        // IV (2nd stage)
        ivreghdfe ///
            `y' (var3 var5 = var6 var7) var4, ///
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

        // First-stage: partial F, coefficient rows
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
end

//---------------------------------------------------------------------------
// 5) Run FE variants (existing + new)
//---------------------------------------------------------------------------
run_fe "fyhu"            "absorb(firm_id user_id yh)"                          "no"  "no"
run_fe "firmbyuseryh"    "absorb(firm_id#user_id yh)"                          "no"  "no"
run_fe "firmyear_match"  "absorb(firm_id#year firm_id#user_id yh)"             "yes" "no"
run_fe "firmyear"        "absorb(firm_id#year yh)"                             "yes" "no"
run_fe "indyear_match"   "absorb(industry_id#year firm_id#user_id yh)"         "yes" "yes"
run_fe "indyear"         "absorb(industry_id#year yh)"                         "yes" "yes"

//---------------------------------------------------------------------------
// 6) Close & export
//---------------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "$RESULT_DIR/consolidated_results.csv", replace ///
    delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "$RESULT_DIR/first_stage_fstats.csv", replace ///
        delimiter(",") quote

display as result "→ main CSV       : $RESULT_DIR/consolidated_results.csv"
display as result "→ first-stage CSV: $RESULT_DIR/first_stage_fstats.csv"

log close
