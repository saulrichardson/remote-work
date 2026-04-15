*============================================================*
* firm_scaling_vacancy_outcomes_htv2_95.do
* Extends the firm-scaling analysis to vacancy intensity by linking the half-
* year firm panel to job-posting counts.  We study vacancy levels, log postings,
* hires-per-posting, and the extensive margin, estimating OLS and 2SLS models
* with firm and time fixed effects while instrumenting remote adoption via
* teleworkability.  Outputs feed the vacancy columns in the scaling tables.
*============================================================*

// 0) Setup environment
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



// 1) Load master firm panel (provides firm_id, yh, covariates)
use "$processed_data/firm_panel.dta", clear

// 2) Prepare output dir & logging
local specname   "firm_scaling_vacancy_outcomes_htv2_95"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 3) Merge in vacancy outcomes (half-year)
preserve
    import delimited using "$processed_data/vacancy/firm_halfyear_panel_MERGED_POST.csv", clear varnames(1)

    // Fail fast: verify required variables exist in the imported CSV
    local required_csv_vars companyname_c yh vacancies ///
        hires_to_vacancies_winsor95_min3
    foreach v of local required_csv_vars {
        capture confirm variable `v'
        if _rc {
            di as error "Missing required variable in vacancy CSV: `v'"
            exit 198
        }
    }

    /* Convert yh to Stata half-year numeric to match master (yh is %th in master) */
    tempvar y_tmp h_tmp yh_num
    gen double `y_tmp' = real(substr(yh,1,4))
    gen double `h_tmp' = real(substr(yh,6,1))
    gen double `yh_num' = (`y_tmp' - 1960)*2 + (`h_tmp' - 1)
    format `yh_num' %th
    rename yh yh_str
    rename `yh_num' yh

    /* Keep only keys + outcomes we need */
    keep companyname_c yh /// keys
         vacancies /// for vacancies_thousands
         hires_to_vacancies_winsor95_min3
    tempfile vac
    save `vac'
restore

gen companyname_c = lower(companyname)
merge 1:1 companyname_c yh using `vac'
// Keep matched sample only
keep if _merge == 3
drop _merge

* Create vacancy level in thousands
capture drop vacancies_thousands
gen double vacancies_thousands = vacancies/1000
label var vacancies_thousands "Vacancies (Thousands)"

tempvar vac_rank_raw vac_rank_denom
bysort yh: egen `vac_rank_raw' = rank(vacancies_thousands), field
bysort yh: egen `vac_rank_denom' = count(vacancies_thousands)
capture drop vacancies_rank_q100
gen double vacancies_rank_q100 = 100 * `vac_rank_raw' / `vac_rank_denom'
label var vacancies_rank_q100 "Job posting rank (pctile)"

capture drop log_vacancies
gen double log_vacancies = .
replace log_vacancies = ln(1 + vacancies) if vacancies > 0
label var log_vacancies "Log job postings (vacancies > 0)"

capture drop any_vacancy
gen byte any_vacancy = (vacancies > 0) if !missing(vacancies)
label var any_vacancy "Indicator for any job postings"

/*
Outcomes used below:
 - vacancies_thousands (levels)
 - vacancies_rank_q100 (within-half-year percentile)
 - log_vacancies (intensive margin, vacancies > 0)
 - hires_to_vacancies_winsor95_min3 (min vacancies = 3, winsor 5/95)
 - any_vacancy (extensive margin indicator)
*/

capture postclose handle
tempfile out
*--- postfile header (main results) -------------------------------------------
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

// (No separate first-stage export in this minimal spec)

// 4) Loop over outcomes (restricted set)
local outcome_vars vacancies_thousands vacancies_rank_q100 log_vacancies hires_to_vacancies_winsor95_min3 any_vacancy

foreach y of local outcome_vars {
    di as text "→ Processing `y'"

     summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // --- OLS ---
     reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)

    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    // --- IV (2nd stage) ---
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst

    local rkf   = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    // (First-stage capture omitted to keep spec minimal)
}

// 5) Close & export to CSV (LaTeX-friendly downstream)
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "(first-stage export omitted in this spec)"

log close
