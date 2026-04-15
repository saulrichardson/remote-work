*============================================================*
* scratch/user_productivity_state_industry_fe_scratch.do
*
* Scratch spec to prototype additional robustness FE variants:
*   • Industry × Year
*   • Industry × Half-Year (yh)
*   • HQ State × Year
*   • HQ State × Half-Year (yh)
*
* This file is NOT part of the production pipeline yet.
* It exists so we can iterate on FE definitions + required columns without
* modifying existing empirical specs.
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional variant argument before bootstrapping paths
* --------------------------------------------------------------------------
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname user_productivity_state_industry_fe_scratch_`panel_variant'

* --------------------------------------------------------------------------
* 1) Bootstrap paths + logging
* --------------------------------------------------------------------------
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

* --------------------------------------------------------------------------
* 2) Load panel once, create derived IDs, save to tempfile for reuse
* --------------------------------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

* Ensure year exists (some panel variants may omit it)
cap confirm variable year
if _rc {
    cap confirm variable yh
    if _rc {
        di as error "Missing `yh` and `year`; cannot construct year."
        exit 198
    }
    gen int year = year(dofh(yh))
}

* Ensure industry_id exists (used for industry×time FE variants)
cap confirm variable industry_id
if _rc {
    di as error "industry_id missing from panel; cannot run industry×time FE variants."
    exit 198
}

* Ensure HQ state exists + create numeric ID for absorb interactions
cap confirm variable hqstate_id
if _rc {
    cap confirm string variable hqstate
    if _rc {
        di as error "hqstate missing from panel; cannot run HQ state×time FE variants."
        exit 198
    }
    encode hqstate, gen(hqstate_id)
    label var hqstate_id "HQ state ID (encoded from hqstate)"
}

tempfile panel_tmp
save `panel_tmp', replace

* --------------------------------------------------------------------------
* 3) Postfiles for results
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

* --------------------------------------------------------------------------
* 4) Helper: run one FE variant across chosen outcomes
* --------------------------------------------------------------------------
global OUTCOMES "total_contributions_q100"

program define run_fe
    args tag feopt

    foreach y of global OUTCOMES {
        use `panel_tmp', clear

        di as text ">> FE tag: `tag' | outcome: `y'"
        summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        * OLS
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

        * IV
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

        * First-stage diagnostics (partial F pulled from e(first))
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

* --------------------------------------------------------------------------
* 5) Prototype FE variants (edit tags/options as needed)
* --------------------------------------------------------------------------
run_fe "indyear"   "absorb(firm_id user_id yh industry_id#year)"
run_fe "indyh"     "absorb(firm_id user_id industry_id#yh)"
run_fe "stateyear" "absorb(firm_id user_id yh hqstate_id#year)"
run_fe "stateyh"   "absorb(firm_id user_id hqstate_id#yh)"

* --------------------------------------------------------------------------
* 6) Export scratch CSVs
* --------------------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", replace delimiter(",") quote

di as result "→ main CSV       : `result_dir'/consolidated_results.csv"
di as result "→ first-stage CSV: `result_dir'/first_stage_fstats.csv"

log close

