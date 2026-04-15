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
*  firm_msa_counts_headcount.do
*  — Baseline IV/OLS with headcount-based MSA count outcomes
*    Outcomes: n_cbsa_headcount, log(1 + n_cbsa_headcount)
*    Spec: firm & time FE, cluster by firm (matches firm_scaling.do)
*============================================================*

// 0) Setup environment
do "../globals.do"

// Setup logging
local specname "firm_msa_counts_headcount"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load firm panel (standard treatment variables)
use "$processed_data/firm_panel.dta", clear

// 2) Merge headcount-based breadth (distinct CBSAs with headcount>0)
preserve
    import delimited "$processed_data/firm_headcount_breadth.csv", clear varnames(1)
    // Ensure merge key name consistency
    rename yh yh_key
    tempfile breadth
    save `breadth'
restore

// Standardize merge key
gen companyname_lower = lower(companyname)

// Build half-year integer key in master for robust merge
capture confirm variable yh_key
if _rc {
    capture confirm variable yh_int
    if !_rc {
        gen long yh_key = yh_int
    }
    else {
        capture confirm variable yh
        if !_rc {
            quietly summarize yh
            // If yh already looks like half-year integer (e.g., 4030..4050)
            if r(N) > 0 & r(min) >= 3000 & r(max) <= 6000 {
                gen long yh_key = yh
            }
            else {
                // Try constructing from year/half or date
                capture confirm variable year
                capture confirm variable half
                if !_rc {
                    gen long yh_key = year*2 + (half==2)
                }
                else {
                    capture confirm variable date
                    if !_rc {
                        gen int _mon = month(date)
                        gen int _year = year(date)
                        gen long yh_key = _year*2 + (_mon>=7)
                        drop _mon _year
                    }
                    else {
                        di as error "ERROR: Could not construct half-year key (yh_key)"
                        exit 198
                    }
                }
            }
        }
        else {
            di as error "ERROR: No yh/yh_int/date to construct yh_key"
            exit 198
        }
    }
}

// Merge
merge 1:1 companyname_lower yh_key using `breadth', keep(1 3) gen(bmerge)
di _n "Breadth merge results:" 
tab bmerge

// 3) Define outcomes
label var n_cbsa_headcount "# CBSAs with headcount > 0 (firm×yh)"

// Resolve total employees for the period (prefer panel totals)
capture confirm variable total_headcount
if _rc {
    // Try common panel names
    capture confirm variable total_employees
    if !_rc {
        gen double total_headcount = total_employees
    }
    else {
        capture confirm variable employeecount
        if !_rc {
            gen double total_headcount = employeecount
        }
        else {
            capture confirm variable headcount
            if !_rc {
                gen double total_headcount = headcount
            }
            else {
                di as error "ERROR: Could not find a total employee count (total_employees/employeecount/headcount)"
                exit 198
            }
        }
    }
}

// Outcome: employees per CBSA (average employees per active CBSA)
gen double emp_per_cbsa = total_headcount / n_cbsa_headcount if n_cbsa_headcount > 0
label var emp_per_cbsa "Employees per CBSA (firm×yh)"

// Robustness log outcome
gen double log_n_cbsa = log(n_cbsa_headcount + 1)
label var log_n_cbsa "log(1 + # CBSAs with headcount)"

// Quick sanity checks
di _n "Summary of outcomes (post-period):"
sum emp_per_cbsa n_cbsa_headcount log_n_cbsa if covid == 1

// 4) Prepare collectors
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome    ///
    str40  param      ///
    double coef se pval pre_mean ///
    double rkf nobs   ///
    using `out', replace

tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

// 5) Baseline regressions
local outcomes emp_per_cbsa n_cbsa_headcount log_n_cbsa

foreach y of local outcomes {
    di _n "→ Processing outcome: `y'"

    // Variation check
    qui sum `y' if !missing(var3, var5, var4)
    if r(N) == 0 | r(sd) == 0 {
        di "  Skipping `y' - insufficient variation"
        continue
    }

    // Pre-period mean (for reference)
    qui sum `y' if covid == 0
    local pre_mean = r(mean)

    // --- OLS ---
    qui reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
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

    // --- IV ---
    qui ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
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

    // First-stage diagnostics (record once for n_cbsa_headcount)
    if "`y'" == "n_cbsa_headcount" {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        qui estimates restore _ivreg2_var3
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var3") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
        }

        qui estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var5") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
        }
    }
}

// 6) Export results
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", replace

di _n "========================================"
di "HEADCOUNT-BASED MSA COUNT ANALYSIS COMPLETE"
di "Results saved to: `result_dir'"
di "========================================"

log close
exit
