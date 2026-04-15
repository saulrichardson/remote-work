*============================================================*
* Asset 04: startup_cutoff_bars_growth_rate_we.png
* Self-contained firm startup-cutoff sweep.
*============================================================*

local asset_stem "04_startup_cutoff_bars_growth_rate_we"

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
log using "$LOG_DIR/`asset_stem'.log", replace text

use "$processed_data/firm_panel.dta", clear

local result_root "$results/`asset_stem'"
capture mkdir "`result_root'"
local result_dir "`result_root'/firm_scaling"
capture mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str4  cutoff ///
    str8  model_type ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local outcomes growth_rate_we join_rate_we leave_rate_we
local cutoffs "5 7 10 12 15"

foreach cutoff of local cutoffs {
    preserve

    tempvar startup_flag
    gen byte `startup_flag' = age <= `cutoff'
    replace startup = `startup_flag'
    replace var4    = covid * `startup_flag'
    replace var5    = remote * covid * `startup_flag'
    replace var7    = `startup_flag' * covid * teleworkable

    foreach y of local outcomes {
        summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        local N = e(N)
        local coeffs : colnames e(b)
        foreach p in var3 var5 var4 {
            local present = strpos(" `coeffs' ", " `p' ")
            if `present' {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            else {
                local b = .
                local se = .
                local pval = .
            }
            post handle ("`cutoff'") ("OLS") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
        }
    }

    foreach y of local outcomes {
        summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
            absorb(firm_id yh) cluster(firm_id)
        local rkf = e(rkf)
        local N = e(N)
        local coeffs : colnames e(b)

        foreach p in var3 var5 var4 {
            local present = strpos(" `coeffs' ", " `p' ")
            if `present' {
                local b    = _b[`p']
                local se   = _se[`p']
                local t    = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            else {
                local b = .
                local se = .
                local pval = .
            }
            post handle ("`cutoff'") ("IV") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
        }
    }

    restore
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

log close
