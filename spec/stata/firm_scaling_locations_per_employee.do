*======================================================================*
* firm_scaling_locations_per_employee.do
* Runs the canonical firm-scaling spec with the outcome equal to the
* ratio of unique LinkedIn locations per firm divided by the time-varying
* employee count.
*======================================================================*

version 17
clear all
set more off

*---- Bootstrap paths -------------------------------------------------*
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



*---- Load firm panel & merge geography counts -----------------------*
use "$processed_data/firm_panel.dta", clear
replace companyname = lower(companyname)

local geo_counts "$processed_data/firm_geography_counts.dta"
if !fileexists("`geo_counts'") {
    di as error "Missing geography counts file: `geo_counts'"
    exit 601
}

merge 1:1 companyname yh using "`geo_counts'", keep(master match) nogen

foreach v in n_states n_msas n_locations {
    replace `v' = 0 if missing(`v')
}

capture confirm numeric variable total_employees
if _rc {
    di as error "total_employees variable missing in firm_panel."
    exit 459
}

gen double states_per_employee = .
replace states_per_employee = n_states / total_employees if total_employees > 0
label var states_per_employee "# States per Employee"

gen double msas_per_employee = .
replace msas_per_employee = n_msas / total_employees if total_employees > 0
label var msas_per_employee "# MSAs per Employee"

gen double locations_per_employee = .
replace locations_per_employee = n_locations / total_employees if total_employees > 0
label var locations_per_employee "# Locations per Employee"

*---- Results setup ---------------------------------------------------*
local specname "firm_scaling_locations_per_employee"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

local fs_done = 0

local outcome_vars states_per_employee msas_per_employee locations_per_employee

foreach outcome of local outcome_vars {
    quietly summarize `outcome' if covid == 0
    local pre_mean = r(mean)

    *--- OLS ----------------------------------------------------------*
    reghdfe `outcome' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    *--- IV -----------------------------------------------------------*
    ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    if !`fs_done' {
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
            post handle_fs ("var3") ("`p'") ///
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
            post handle_fs ("var5") ("`p'") ///
                (`b') (`se') (`pval') ///
                (`F5') (`rkf') (`N_fs')
        }

        local fs_done 1
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

di as result "✓ Locations-per-employee spec completed → `result_dir'"
capture log close
