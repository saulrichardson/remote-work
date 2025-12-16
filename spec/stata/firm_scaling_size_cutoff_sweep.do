*============================================================*
* firm_scaling_size_cutoff_sweep.do
* Sweep startup size cutoffs (employees as of 2019H2) for firm outcomes.
*============================================================*

// Bootstrap
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

// Data
use "$processed_data/firm_panel.dta", clear

local specname "firm_scaling_size_cutoff_sweep"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

// Merge size baseline
tempfile size_lookup
local size_dta "$clean_data/firm_size_2019h2.dta"
local size_csv "$clean_data/firm_size_2019h2.csv"
preserve
    capture confirm file "`size_dta'"
    if !_rc {
        use "`size_dta'", clear
    }
    else {
        capture confirm file "`size_csv'"
        if _rc {
            di as error "Missing firm_size_2019h2.{dta,csv}. Run python src/py/build_firm_size_baseline.py first."
            exit 601
        }
        import delimited using "`size_csv'", clear
    }
    save "`size_lookup'", replace
restore

merge m:1 companyname using "`size_lookup'", keep(3) nogen

local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str6 cutoff ///
    str8 model_type ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str6 cutoff ///
    str8 endovar ///
    str40 param ///
    double coef se pval partialF rkf nobs ///
    using `out_fs', replace

local outcomes growth_rate_we join_rate_we leave_rate_we
local cutoffs "50 100 150 200 500"

foreach cutoff of local cutoffs {
    di as text "→ firm cutoff <= `cutoff' employees"
    preserve

    replace startup = size_2019h2 <= `cutoff' if size_2019h2 < .
    replace var4    = covid * startup
    replace var5    = remote * covid * startup
    replace var7    = startup * covid * teleworkable

    local fs_done 0
    foreach y of local outcomes {
        summarize `y' if covid==0, meanonly
        local pre_mean = r(mean)

        reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
        local N = e(N)
        foreach p in var3 var5 var4 {
            local b = _b[`p']
            local se = _se[`p']
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("`cutoff'") ("OLS") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
        }
    }

    foreach y of local outcomes {
        summarize `y' if covid==0, meanonly
        local pre_mean = r(mean)

        ivreghdfe `y' (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id) savefirst
        local rkf = e(rkf)
        local N = e(N)
        foreach p in var3 var5 var4 {
            local b = _b[`p']
            local se = _se[`p']
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("`cutoff'") ("IV") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
        }

        if !`fs_done' {
            matrix FS = e(first)
            local F3 = FS[4,1]
            local F5 = FS[4,2]

            estimates restore _ivreg2_var3
            local N_fs = e(N)
            foreach p in var6 var7 var4 {
                local b = _b[`p']
                local se = _se[`p']
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_fs ("`cutoff'") ("var3") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
            }

            capture estimates restore _ivreg2_var5
            if !_rc {
                local N_fs = e(N)
                foreach p in var6 var7 var4 {
                    local b = _b[`p']
                    local se = _se[`p']
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    post handle_fs ("`cutoff'") ("var5") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
                }
            }
            local fs_done 1
        }
    }

    restore
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

di as result "→ cutoff sweep CSV : `result_dir'/consolidated_results.csv"

capture log close
