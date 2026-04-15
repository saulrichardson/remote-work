*============================================================*
* user_productivity_startup_cutoff_15.do
* Run the baseline user-level spec with a single startup age
* cutoff of 15 years (no sweep) to isolate failures quickly.
* Mirrors user_productivity_startup_cutoff_sweep.do for one
* cutoff value.
*============================================================*

* Optional argument: panel variant (default: precovid)
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_startup_cutoff15_`panel_variant'

// Bootstrap paths
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

// Load worker-level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear
drop _merge

local cutoff 15
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str4  cutoff ///
    str8  model_type ///
    str40 outcome ///
    str40 param   ///
    double coef se pval pre_mean ///
    double rkf nobs   ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str4  cutoff ///
    str8  endovar ///
    str40 param   ///
    double coef se pval partialF rkf nobs ///
    using `out_fs', replace

local outcomes total_contributions_q100 restricted_contributions_q100

di as text "→ Running OLS/IV with startup cutoff <= `cutoff' years"
preserve

tempvar startup_flag
gen byte `startup_flag' = age <= `cutoff'
replace startup = `startup_flag'
replace var4    = covid * `startup_flag'
replace var5    = remote * covid * `startup_flag'
replace var7    = `startup_flag' * covid * company_teleworkable

local fs_done 0
foreach y of local outcomes {
    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `y' var3 var5 var4, absorb(user_id firm_id yh) ///
        vce(cluster user_id)

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
            local b    = .
            local se   = .
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

    ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(user_id firm_id yh) cluster(user_id) savefirst

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
            local b    = .
            local se   = .
            local pval = .
        }

        post handle ("`cutoff'") ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    if !`fs_done' {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        estimates restore _ivreg2_var3
        local N_fs = e(N)
        local coeffs : colnames e(b)
        foreach p in var6 var7 var4 {
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

            post handle_fs ("`cutoff'") ("var3") ("`p'") ///
                (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
        }

        capture estimates restore _ivreg2_var5
        if !_rc {
            local N_fs = e(N)
            local coeffs : colnames e(b)
            foreach p in var6 var7 var4 {
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

                post handle_fs ("`cutoff'") ("var5") ("`p'") ///
                    (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
            }
        }

        local fs_done 1
    }
}

restore

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

di as result "→ cutoff 15 CSV : `result_dir'/consolidated_results.csv"
capture log close
