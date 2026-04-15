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
*  spec/firm_scaling_vacancy_outcomes.do
*  — Baseline OLS/IV on vacancy outcomes (half-year)
*============================================================*

// 0) Setup environment
do "../globals.do"

// 1) Load master firm panel (provides firm_id, yh, covariates)
use "$processed_data/firm_panel.dta", clear

// 2) Prepare output dir & logging
local specname   "firm_scaling_vacancy_outcomes"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 3) Merge in vacancy outcomes (half-year)
preserve
    import delimited using "$processed_data/vacancy/firm_halfyear_panel_MERGED_POST.csv", clear varnames(1)
    
    // Fail fast: verify required variables exist in the imported CSV
    local required_csv_vars companyname companyname_c yh vacancies vpe_pc_winsor ///
        fill_rate fill_rate_min1 fill_rate_min2 fill_rate_min3 fill_rate_min4 fill_rate_min5 ///
        hires_to_vacancies_winsor ///
        hires_to_vacancies_winsor_min1 hires_to_vacancies_winsor_min2 hires_to_vacancies_winsor_min3 hires_to_vacancies_winsor_min4 hires_to_vacancies_winsor_min5 ///
        hires_to_vacancies_winsor95_min1 hires_to_vacancies_winsor95_min2 hires_to_vacancies_winsor95_min3 hires_to_vacancies_winsor95_min4 hires_to_vacancies_winsor95_min5
    foreach v of local required_csv_vars {
        capture confirm variable `v'
        if _rc {
            di as error "Missing required variable in vacancy CSV: `v'"
            exit 198
        }
    }
    /* Normalize a couple of Stata-hostile names from CSV */
    capture confirm variable filled_3mo
    if _rc==0 rename filled_3mo filled_le_3mo
    capture confirm variable prop_filled_3mo
    if _rc==0 rename prop_filled_3mo prop_filled_le_3mo
    /* Convert yh to Stata half-year numeric to match master (yh is %th in master) */
    tempvar y_tmp h_tmp yh_num
    gen double `y_tmp' = real(substr(yh,1,4))
    gen double `h_tmp' = real(substr(yh,6,1))
    gen double `yh_num' = (`y_tmp' - 1960)*2 + (`h_tmp' - 1)
    format `yh_num' %th
    rename yh yh_str
    rename `yh_num' yh
    /* Keep only keys + outcomes we need */
    keep companyname companyname_c yh /// keys
         vacancies /// levels (raw)
         vpe_pc_winsor upe_pc_winsor /// ratios to pre-COVID employees (winsor)
         fill_rate_min1 fill_rate_min2 fill_rate_min3 fill_rate_min4 fill_rate_min5 fill_rate /// fill-rate with vacancy cutoffs and alias
         hires_to_vacancies_winsor /// legacy alias (min5 p01/99)
         hires_to_vacancies_winsor_min1 hires_to_vacancies_winsor_min2 hires_to_vacancies_winsor_min3 hires_to_vacancies_winsor_min4 hires_to_vacancies_winsor_min5 ///
         hires_to_vacancies_winsor95_min1 hires_to_vacancies_winsor95_min2 hires_to_vacancies_winsor95_min3 hires_to_vacancies_winsor95_min4 hires_to_vacancies_winsor95_min5
    tempfile vac
    save `vac'
restore

gen companyname_c = lower(companyname)
merge 1:1 companyname_c yh using `vac'
// Report merge summary; proceed with matched sample
count if _merge == 2
local using_only = r(N)
count if _merge == 1
local master_only = r(N)
local matched = _N - `using_only' - `master_only'
local mergesum "Merge summary: matched=`matched' using-only=`using_only' master-only=`master_only'"
di as text "`mergesum'"
keep if _merge == 3
drop _merge

* Create canonical vacancy level in thousands (no fallback to raw counts)
capture drop vacancies_thousands
gen double vacancies_thousands = vacancies/1000
label var vacancies_thousands "Vacancies (Thousands)"

* Label key constructed outcomes for clarity in tables/logs
capture confirm variable fill_rate
if _rc==0 label var fill_rate "Proportion Filled (≥5 vacancies)"
forvalues k = 1/5 {
    capture confirm variable fill_rate_min`k'
    if _rc==0 label var fill_rate_min`k' "Proportion Filled (≥`k' vacancies)"
}
capture confirm variable hires_to_vacancies_winsor
if _rc==0 label var hires_to_vacancies_winsor "Hires per vacancy (winsor 1/99, ≥5 vacancies)"
forvalues k = 1/5 {
    capture confirm variable hires_to_vacancies_winsor_min`k'
    if _rc==0 label var hires_to_vacancies_winsor_min`k' "Hires per vacancy (winsor 1/99, ≥`k' vacancies)"
    capture confirm variable hires_to_vacancies_winsor95_min`k'
    if _rc==0 label var hires_to_vacancies_winsor95_min`k' "Hires per vacancy (winsor 5/95, ≥`k' vacancies)"
}
capture confirm variable vpe_pc_winsor
if _rc==0 label var vpe_pc_winsor "Vacancies per pre-COVID employees (winsor)"

* (Percentile outcomes omitted)

/*
Outcomes used below:
 - vacancies (raw) and vacancies_thousands
 - vpe_pc_winsor, upe_pc_winsor
 - fill_rate (and min1..min5 variants)
 - hires_to_vacancies_winsor (and min1..min5, 1/99 and 5/95 variants)
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

*------------------------------------------------------------------
*  First-stage results → first_stage.csv
*------------------------------------------------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

// 4) Loop over outcomes
// Vacancies: raw, per-thousand (scaling check), and normalized by pre-COVID employment
local outcome_vars vacancies vacancies_thousands /// vacancies (raw + scaled)
                   vpe_pc_winsor /// vacancies per pre-COVID employees (winsor)
                   fill_rate fill_rate_min1 fill_rate_min2 fill_rate_min3 fill_rate_min4 fill_rate_min5 /// fill rate with min-vacancy cutoffs
                   hires_to_vacancies_winsor /// legacy alias (min5 p01/99)
                   hires_to_vacancies_winsor_min1 hires_to_vacancies_winsor_min2 hires_to_vacancies_winsor_min3 hires_to_vacancies_winsor_min4 hires_to_vacancies_winsor_min5 ///
                   hires_to_vacancies_winsor95_min1 hires_to_vacancies_winsor95_min2 hires_to_vacancies_winsor95_min3 hires_to_vacancies_winsor95_min4 hires_to_vacancies_winsor95_min5

local fs_done = 0

foreach y of local outcome_vars {
    di as text "→ Processing `y'"

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // --- OLS ---
    quietly reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)

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
    quietly ivreghdfe ///
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

    // --- FIRST STAGE: only once on first loop pass ---
    if !`fs_done' {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        /* -------- var3 first stage -------------------------------- */
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

        /* -------- var5 first stage -------------------------------- */
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

* Percentile-form outcomes omitted per request

// 5) Close & export to CSV (LaTeX-friendly downstream)
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
