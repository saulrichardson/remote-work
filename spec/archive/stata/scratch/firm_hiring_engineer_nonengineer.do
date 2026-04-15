// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

*============================================================*
* firm_hiring_engineer_nonengineer.do
* ------------------------------------------------------------
* Regression table: Remote × Post impact on engineer hires
* Mirrors main firm-growth specification (firm & half-year FE,
* Remote × Post + Startup interactions) with OLS + IV.
*============================================================*

clear all
set more off

capture log close
log using "firm_hiring_engineer_nonengineer.log", replace text

// Resolve data/results roots (works from repo or subdir)
capture confirm file "$processed_data/firm_panel.dta"
if _rc {
    capture confirm file "data/processed/firm_panel.dta"
    if !_rc {
        global processed_data "data/processed"
        global base_results  "results"
    }
    else {
        capture confirm file "../data/processed/firm_panel.dta"
        if !_rc {
            global processed_data "../data/processed"
            global base_results  "../results"
        }
        else {
            global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
            global base_results  "/Users/saul/Dropbox/Remote Work Startups/main/results"
        }
    }
}

local specname "firm_hiring_engineer_nonengineer"
local result_dir "$base_results/raw/`specname'"
cap mkdir "`result_dir'"

display "============================================================"
display "Engineer vs Non-Engineer hiring regressions"
display "Outcome units: engineer headcount growth" 
display "Cutoffs: 5–95 winsorization applied to outcomes"
display "============================================================"

// ------------------------------------------------------------
// STEP 1: Firm baseline sample with Emp_pre (2019 baseline)
// ------------------------------------------------------------
use "$processed_data/firm_panel.dta", clear

gen companyname_c = lower(companyname)
format date %td

gen year = year(date)
label var year "Calendar year"

gen byte pre_covid = (year == 2019)

bysort firm_id: egen emp_pre_tmp = mean(total_employees) if pre_covid & total_employees > 0
bysort firm_id: egen Emp_pre = max(emp_pre_tmp)
drop emp_pre_tmp

// Fallback: first non-missing employment at/before 2019

gen pre_level = total_employees if year <= 2019 & total_employees > 0
bysort firm_id (yh): replace pre_level = pre_level[_n-1] if missing(pre_level)
bysort firm_id: replace Emp_pre = pre_level if missing(Emp_pre)
drop pre_level

drop if missing(Emp_pre) | Emp_pre <= 0

display "Firms with valid pre-COVID employment: " %9.0fc _N

keep firm_id companyname companyname_c yh covid startup var3 var4 var5 var6 var7 Emp_pre

tempfile firm_base
save `firm_base'

// ------------------------------------------------------------
// STEP 2: Engineer headcount levels per yh
// ------------------------------------------------------------
import delimited "$processed_data/role_k7_scaling_growth.csv", clear

keep companyname role_k7 year half employee_count prev_count

keep if role_k7 == "Engineer"

// Guard against missing counts
replace employee_count = 0 if missing(employee_count)
replace prev_count     = 0 if missing(prev_count)

gen companyname_c = lower(companyname)

gen yh = yh(year, half)

collapse (sum) employee_count prev_count, by(companyname_c yh)

rename employee_count eng_headcount
rename prev_count     eng_headcount_lag

tempfile hires
save `hires'

display "Collapsed engineer headcount saved"

// ------------------------------------------------------------
// STEP 3: Merge outcomes and build growth rate
// ------------------------------------------------------------
use `firm_base', clear
merge 1:1 companyname_c yh using `hires'

// Keep firm-panel observations; fill missing headcount values with 0
keep if inlist(_merge, 1, 3)
replace eng_headcount     = 0 if missing(eng_headcount)
replace eng_headcount_lag = 0 if missing(eng_headcount_lag)
drop _merge

// Engineer growth rate relative to prior half (parallel to firm growth)
gen eng_growth_rate = (eng_headcount / eng_headcount_lag) - 1 if eng_headcount_lag > 0
label var eng_growth_rate "Engineer growth rate"

// Winsorize outcomes at 5/95 percentiles
winsor2 eng_growth_rate, cuts(5 95) suffix(_w95)

label var eng_growth_rate_w95 "Engineer growth rate"

display _n "Summary stats (pre-COVID means):"
summarize eng_growth_rate_w95 if covid == 0

// ------------------------------------------------------------
// STEP 4: Regression loop (OLS + IV)
// ------------------------------------------------------------
capture postclose handle
capture postclose handle_fs

tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome ///
    str12  param ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

// First-stage storage (reported once)
tempfile out_fs
postfile handle_fs ///
    str8   endovar ///
    str12  param ///
    double coef se pval partialF rkf nobs ///
    using `out_fs', replace

local fs_done 0

local yvar eng_growth_rate_w95
local ylab "Engineer growth rate"

display _n "→ Outcome: `ylab'"

summarize `yvar' if covid == 0, meanonly
local pre_mean = r(mean)

// ----- OLS -----
reghdfe `yvar' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
local N = e(N)
foreach p in var3 var5 var4 {
    local b  = _b[`p']
    local se = _se[`p']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("`ylab'") ("`p'") (`b') (`se') (`pv') (`pre_mean') (.) (`N')
}

// ----- IV -----
ivreghdfe `yvar' (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) vce(cluster firm_id) savefirst

local rkf = e(rkf)
local N   = e(N)

matrix FS = e(first)
local F3 = FS[4,1]
local F5 = FS[4,2]

foreach p in var3 var5 var4 {
    local b  = _b[`p']
    local se = _se[`p']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("`ylab'") ("`p'") (`b') (`se') (`pv') (`pre_mean') (`rkf') (`N')
}

if !`fs_done' {
    estimates restore _ivreg2_var3
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b  = _b[`p']
        local se = _se[`p']
        local t  = `b'/`se'
        local pv = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("var3") ("`p'") (`b') (`se') (`pv') (`F3') (`rkf') (`N_fs')
    }

    estimates restore _ivreg2_var5
    local N_fs = e(N)
    foreach p in var6 var7 var4 {
        local b  = _b[`p']
        local se = _se[`p']
        local t  = `b'/`se'
        local pv = 2*ttail(e(df_r), abs(`t'))
        post handle_fs ("var5") ("`p'") (`b') (`se') (`pv') (`F5') (`rkf') (`N_fs')
    }

    local fs_done 1
}

// ------------------------------------------------------------
// STEP 5: Export consolidated results
// ------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote


capture log close
