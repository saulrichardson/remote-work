*============================================================*
* Asset 08: firm_event_study_hires_per_job_posting_ols.png
*============================================================*

local asset_stem "08_firm_event_study_hires_per_job_posting_ols"
local outcome "hires_to_vacancies_winsor"
local output_file "ols_hires_to_vacancies_winsor.csv"

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

local result_dir "$results/`asset_stem'"
cap mkdir "`result_dir'"

use "$processed_data/firm_panel.dta", clear

preserve
    import delimited using "$processed_data/vacancy/firm_halfyear_panel_MERGED_POST.csv", clear varnames(1)

    local required_csv_vars companyname yh vacancies hires_to_vacancies_winsor
    foreach v of local required_csv_vars {
        capture confirm variable `v'
        if _rc {
            di as error "Missing required vacancy variable: `v'"
            exit 198
        }
    }

    tempvar y_tmp h_tmp yh_num
    gen double `y_tmp' = real(substr(yh, 1, 4))
    gen double `h_tmp' = real(substr(yh, 6, 1))
    gen double `yh_num' = (`y_tmp' - 1960) * 2 + (`h_tmp' - 1)
    format `yh_num' %th
    rename yh yh_str
    rename `yh_num' yh

    capture confirm variable companyname_c
    if _rc {
        gen companyname_c = lower(companyname)
    }
    else {
        replace companyname_c = lower(companyname)
    }
    keep companyname companyname_c yh vacancies hires_to_vacancies_winsor
    tempfile vacancy_panel
    save `vacancy_panel'
restore

gen companyname_c = lower(companyname)
merge 1:1 companyname_c yh using `vacancy_panel'

count if _merge == 2
local using_only = r(N)
count if _merge == 1
local master_only = r(N)
local matched = _N - `using_only' - `master_only'
di as text "Merge summary (vacancy): matched=`matched' using-only=`using_only' master-only=`master_only'"

keep if _merge == 3
drop _merge

capture confirm variable hires_to_vacancies_winsor
if _rc == 0 label var hires_to_vacancies_winsor "Hires per vacancy (winsor 1/99, >=5 vacancies)"

tab yh, gen(time)

tempvar tmpindex
preserve
    contract yh
    sort yh
    gen `tmpindex' = _n
    local target19h2 = yh(2019, 2)
    quietly summarize `tmpindex' if yh == `target19h2'
    local idx19h2 = r(mean)
    di as text "Index for 2019H2 is `idx19h2'"
    gen str7 period_label = subinstr(string(yh, "%th"), "h", "H", .)
    keep yh `tmpindex' period_label
    rename `tmpindex' period
    tempfile yhmap
    save `yhmap'
restore

gen byte dummy_2019h2 = time`idx19h2'
label var dummy_2019h2 "Indicator for 2019H2"
tab yh dummy_2019h2

preserve
    contract yh
    local total_periods = _N
restore

local rem_vars ""
local rem_start_vars ""
local startup_vars ""
forval t = 1/`total_periods' {
    gen rem_`t'       = remote * time`t'
    gen startup_`t'   = startup * time`t'
    gen rem_start_`t' = remote * time`t' * startup
    if `t' == `idx19h2' continue
    local rem_vars `rem_vars' rem_`t'
    local rem_start_vars `rem_start_vars' rem_start_`t'
    local startup_vars `startup_vars' startup_`t'
}

reghdfe `outcome' `rem_vars' `rem_start_vars' `startup_vars', absorb(firm_id yh) vce(cluster firm_id)

matrix define escoef = J(`total_periods', 3, .)
forval i = 1/`total_periods' {
    if `i' == `idx19h2' continue
    local b = _b[rem_start_`i']
    local se = _se[rem_start_`i']
    matrix escoef[`i', 1] = `b'
    matrix escoef[`i', 2] = `b' - 1.96 * `se'
    matrix escoef[`i', 3] = `b' + 1.96 * `se'
}
matrix colnames escoef = b lb ub

preserve
    clear
    svmat double escoef, names(col)
    gen period = _n
    gen event_time = period - `idx19h2'
    gen omitted = period == `idx19h2'
    replace b = . if omitted
    replace lb = . if omitted
    replace ub = . if omitted
    merge 1:1 period using `yhmap', nogen
    gen str8 estimator = "OLS"
    gen str80 outcome = "`outcome'"
    order outcome estimator period period_label event_time omitted b lb ub yh
    export delimited using "`result_dir'/`output_file'", replace
restore

log close
