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
*  firm_scaling_wages_precovid_userpanel.do
*  — Firm-level wage regressions using salary aggregates that
*    are constructed directly from the *precovid* user panel.
*    Mirrors firm_scaling_wages.do but collapses the user panel
*    to firm × half-year salary moments on the fly.
*============================================================*

// 0) Setup environment
do "../globals.do"

// 1) Load master panel
use "$processed_data/firm_panel.dta", clear

// 2) Prepare output dir & tempfile
local specname   "firm_scaling_wages_precovid_userpanel"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

gen companyname_c = lower(companyname)
replace companyname_c = strtrim(companyname_c)

* Collapse precovid user panel to firm × half-year salary aggregates
preserve
    use "$processed_data/user_panel_precovid.dta", clear

    gen companyname_c = lower(strtrim(companyname))
    drop if missing(companyname_c)

    capture confirm numeric variable salary
    if _rc {
        quietly destring salary, replace
    }
    drop if missing(salary) | salary <= 0

    capture confirm numeric variable year
    if _rc {
        destring year, replace
    }

    capture confirm numeric variable half
    if _rc {
        destring half, replace
    }

    drop if missing(year) | missing(half)
    capture drop yh
    gen long yh = yh(year, half)

    collapse ///
        (mean)    salary_mean = salary ///
        (sum)     salary_total = salary ///
        (count)   salary_n = salary ///
        (sd)      salary_sd = salary ///
        (median)  salary_p50 = salary, ///
        by(companyname_c yh)

    tempfile wage_panel
    save `wage_panel'
restore

merge 1:1 companyname_c yh using `wage_panel', keep(match master) nogen

// Construct log outcomes (positive support already ensured in collapse)
capture drop log_salary_mean log_salary_total
gen double log_salary_mean  = .
replace log_salary_mean = ln(salary_mean)  if salary_mean  > 0
label var log_salary_mean "Log of mean salary (precovid user panel)"

gen double log_salary_total = .
replace log_salary_total = ln(salary_total) if salary_total > 0
label var log_salary_total "Log of total salary (precovid user panel)"

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
*  First-stage results → first_stage_fstats.csv
*------------------------------------------------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

// 3) Loop over outcomes
local outcome_vars salary_mean salary_total log_salary_mean log_salary_total

local fs_done = 0

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
                                        (.) (`N')                 // dot for rkf, then nobs
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
		*--- inside the IV loop -------------------------------------------------------
                post handle ("IV") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')            // rkf, then nobs
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

// 4) Close & export to CSV
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

* --- write first-stage CSV -----------------------------------------
postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
        replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
