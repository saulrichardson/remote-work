*============================================================*
* Asset 04: firm_scaling_precovid_cols1_4.tex
*           firm_scaling_precovid_cols5_6.tex
* Unified self-contained owner for the active firm-scaling table family.
*============================================================*

args sample_variant
if "`sample_variant'" == "" local sample_variant "precovid"
if "`sample_variant'" != "precovid" {
    di as error "Asset 04 only supports the precovid firm panel variant."
    exit 198
}

local asset_stem "04_firm_scaling_precovid"

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

local result_root "$results/`asset_stem'"
cap mkdir "`result_root'"
cap mkdir "`result_root'/growth_baseline_main_effect"
cap mkdir "`result_root'/growth_interacted_columns"
cap mkdir "`result_root'/vacancy_interacted_columns"
cap mkdir "`result_root'/first_stage"

capture which reghdfe
if _rc {
    di as error "Required package 'reghdfe' not found."
    exit 199
}
capture which ivreghdfe
if _rc {
    di as error "Required package 'ivreghdfe' not found."
    exit 199
}

local firm_panel "$processed_data/firm_panel.dta"
capture confirm file "`firm_panel'"
if _rc {
    di as error "Missing firm panel: `firm_panel'"
    exit 601
}

di as text "Running unified firm-scaling family owner from `firm_panel'"

*------------------------------------------------------------*
* Section 1: Columns 1-4 fragment (growth / join / leave)
*------------------------------------------------------------*
di as text "Section 1: exporting growth baseline main-effect branch"
use "`firm_panel'", clear

capture postclose handle_initial
tempfile out_initial
postfile handle_initial ///
    str8   model_type ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out_initial', replace

local outcome_name growth_rate_we
summarize `outcome_name' if covid == 0, meanonly
local pre_mean = r(mean)

reghdfe `outcome_name' var3 var4, absorb(firm_id yh) vce(cluster firm_id)
local N = e(N)
foreach p in var3 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_initial ("OLS") ("`outcome_name'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') ///
        (.) (`N')
}

ivreghdfe `outcome_name' (var3 = var6) var4, ///
    absorb(firm_id yh) vce(cluster firm_id) savefirst
local rkf = e(rkf)
local N = e(N)
foreach p in var3 var4 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle_initial ("IV") ("`outcome_name'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') ///
        (`rkf') (`N')
}

postclose handle_initial
use `out_initial', clear
export delimited using "`result_root'/growth_baseline_main_effect/consolidated_results.csv", replace delimiter(",") quote

di as text "Section 1: exporting growth interacted branch"
use "`firm_panel'", clear

capture postclose handle_growth
tempfile out_growth
postfile handle_growth ///
    str8   model_type ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out_growth', replace

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

local outcome_vars growth_rate_we join_rate_we leave_rate_we
foreach outcome_name of local outcome_vars {
    summarize `outcome_name' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `outcome_name' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_growth ("OLS") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe ///
        `outcome_name' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_growth ("IV") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    if "`outcome_name'" == "growth_rate_we" {
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
            post handle_fs ("firm_time_fe") ("`outcome_name'") ("var3") ("`p'") ///
                (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
        }

        estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("firm_time_fe") ("`outcome_name'") ("var5") ("`p'") ///
                (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
        }
    }
}

postclose handle_growth
use `out_growth', clear
export delimited using "`result_root'/growth_interacted_columns/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_root'/first_stage/consolidated_results.csv", replace delimiter(",") quote

*------------------------------------------------------------*
* Section 2: Columns 5-6 fragment (vacancy outcomes)
*------------------------------------------------------------*
di as text "Section 2: exporting vacancy interacted branch"
use "`firm_panel'", clear

preserve
    import delimited using "$processed_data/vacancy/firm_halfyear_panel_MERGED_POST.csv", clear varnames(1)

    local required_csv_vars companyname_c yh vacancies ///
        hires_to_vacancies_winsor95_min3
    foreach v of local required_csv_vars {
        capture confirm variable `v'
        if _rc {
            di as error "Missing required variable in vacancy CSV: `v'"
            exit 198
        }
    }

    tempvar y_tmp h_tmp yh_num
    gen double `y_tmp' = real(substr(yh,1,4))
    gen double `h_tmp' = real(substr(yh,6,1))
    gen double `yh_num' = (`y_tmp' - 1960)*2 + (`h_tmp' - 1)
    format `yh_num' %th
    rename yh yh_str
    rename `yh_num' yh

    keep companyname_c yh vacancies hires_to_vacancies_winsor95_min3
    tempfile vac
    save `vac'
restore

gen companyname_c = lower(companyname)
merge 1:1 companyname_c yh using `vac'
keep if _merge == 3
drop _merge

capture drop vacancies_thousands
gen double vacancies_thousands = vacancies / 1000
label var vacancies_thousands "Vacancies (Thousands)"

capture drop any_vacancy
gen byte any_vacancy = (vacancies > 0) if !missing(vacancies)
label var any_vacancy "Indicator for any job postings"

capture postclose handle_vacancy
tempfile out_vacancy
postfile handle_vacancy ///
    str8   model_type ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out_vacancy', replace

local vacancy_outcomes vacancies_thousands hires_to_vacancies_winsor95_min3 any_vacancy
foreach outcome_name of local vacancy_outcomes {
    summarize `outcome_name' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `outcome_name' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_vacancy ("OLS") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe ///
        `outcome_name' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle_vacancy ("IV") ("`outcome_name'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }
}

postclose handle_vacancy
use `out_vacancy', clear
export delimited using "`result_root'/vacancy_interacted_columns/consolidated_results.csv", replace delimiter(",") quote

di as result "Unified firm-scaling raw exports written under `result_root'"
log close
