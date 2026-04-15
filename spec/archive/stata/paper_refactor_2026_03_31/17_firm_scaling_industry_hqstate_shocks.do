*============================================================*
* firm_scaling_industry_hqstate_shocks.do
*
* Robustness table inputs: firm FE + time-varying industry and HQ-state shocks.
*
* Outcome: growth_rate_we
* Models:  OLS + IV (teleworkability instruments)
*
* Columns (fe_tag):
*   1) ind_yh    : firm FE + industry×half-year shocks
*   2) state_yh  : firm FE + HQ-state×half-year shocks
*   3) both_yh   : firm FE + industry×yh + HQ-state×yh
*
* Notes:
* - We deliberately do NOT include plain `yh` once interacting shocks are present.
* - Sample is allowed to vary by FE column (no upfront common-sample restriction).
*============================================================*

* --------------------------------------------------------------------------
* 0) Bootstrap paths + logging
* --------------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

local specname "firm_scaling_industry_hqstate_shocks"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

* --------------------------------------------------------------------------
* 1) Load firm panel and required IDs
* --------------------------------------------------------------------------
use "$processed_data/firm_panel.dta", clear

cap confirm variable firm_id
if _rc {
    di as error "Missing firm_id in firm panel."
    exit 198
}
cap confirm variable yh
if _rc {
    di as error "Missing yh in firm panel."
    exit 198
}
cap confirm variable covid
if _rc {
    di as error "Missing covid in firm panel."
    exit 198
}
cap confirm variable industry_id
if _rc {
    di as error "Missing industry_id in firm panel."
    exit 198
}
cap confirm string variable hqstate
if _rc {
    di as error "Missing string hqstate in firm panel."
    exit 198
}
foreach v in growth_rate_we startup remote teleworkable var3 var4 var5 var6 var7 {
    cap confirm variable `v'
    if _rc {
        di as error "Missing required variable `v' in firm panel."
        exit 198
    }
}

capture drop hqstate_id
encode hqstate, gen(hqstate_id)
label var hqstate_id "HQ state ID (encoded from hqstate)"

tempfile panel_tmp
save `panel_tmp', replace
global PANEL_TMP "`panel_tmp'"

* --------------------------------------------------------------------------
* 2) Results setup (postfiles)
* --------------------------------------------------------------------------
local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

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

global OUTCOMES "growth_rate_we"

program define run_fe
    args tag feopt

    foreach y of global OUTCOMES {
        use "$PANEL_TMP", clear

        * ---------------- OLS ----------------
        reghdfe `y' var3 var5 var4, `feopt' vce(cluster firm_id)
        local N = e(N)
        quietly summarize `y' if e(sample) & covid == 0, meanonly
        local pre_mean = r(mean)

        foreach p in var3 var5 var4 {
            local b  = _b[`p']
            local se = _se[`p']
            if inlist("`p'", "var3", "var5") & missing(`se') {
                di as error "OLS: `p' omitted (likely collinear) under fe_tag=`tag'."
                exit 498
            }
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
        }

        * ---------------- IV ----------------
        ivreghdfe ///
            `y' (var3 var5 = var6 var7) var4, ///
            `feopt' vce(cluster firm_id) savefirst

        local rkf = e(rkf)
        local N = e(N)
        quietly summarize `y' if e(sample) & covid == 0, meanonly
        local pre_mean = r(mean)

        foreach p in var3 var5 var4 {
            local b  = _b[`p']
            local se = _se[`p']
            if inlist("`p'", "var3", "var5") & missing(`se') {
                di as error "IV: `p' omitted (likely collinear) under fe_tag=`tag'."
                exit 498
            }
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
        }

        * ---------------- First stage ----------------
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        estimates restore _ivreg2_var3
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b  = _b[`p']
            local se = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F3') (`rkf') (`N_fs')
        }

        estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b  = _b[`p']
            local se = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F5') (`rkf') (`N_fs')
        }
    }
end

* --------------------------------------------------------------------------
* 3) Run FE variants (3-column robustness table)
* --------------------------------------------------------------------------
run_fe "ind_yh"   "absorb(firm_id industry_id#yh)"
run_fe "state_yh" "absorb(firm_id hqstate_id#yh)"
run_fe "both_yh"  "absorb(firm_id industry_id#yh hqstate_id#yh)"

* --------------------------------------------------------------------------
* 4) Export
* --------------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", replace delimiter(",") quote

di as result "→ main CSV       : `result_dir'/consolidated_results.csv"
di as result "→ first-stage CSV: `result_dir'/first_stage_fstats.csv"
capture log close
