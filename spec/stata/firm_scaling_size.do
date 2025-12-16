*============================================================*
* firm_scaling_size.do
* Firm outcomes with startup defined by size (employees at 2019H2).
* Default cutoff: 150 employees.
*============================================================*

// Bootstrap paths
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

// Load firm panel
use "$processed_data/firm_panel.dta", clear

local specname "firm_scaling_size"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

// Merge firm size baseline
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

// Overwrite startup interactions with size cutoff
replace startup = size_2019h2 <= 150 if size_2019h2 < .
replace var4    = covid * startup
replace var5    = remote * covid * startup
replace var7    = startup * covid * teleworkable

local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str8  model_type ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8  endovar ///
    str40 param   ///
    double coef se pval partialF rkf nobs ///
    using `out_fs', replace

local outcomes growth_rate_we join_rate_we leave_rate_we
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
        post handle ("OLS") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    ivreghdfe `y' (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b = _b[`p']
        local se = _se[`p']
        local t = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
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
            post handle_fs ("var3") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
        }

        capture estimates restore _ivreg2_var5
        if !_rc {
            local N_fs = e(N)
            foreach p in var6 var7 var4 {
                local b = _b[`p']
                local se = _se[`p']
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
                post handle_fs ("var5") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
            }
        }
        local fs_done 1
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

di as result "→ output : `result_dir'/consolidated_results.csv"
di as result "→ first-stage : `result_dir'/first_stage.csv"

capture log close
