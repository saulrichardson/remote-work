*====================================================================*
*  firm_sales.do
*  ------------------------------------------------------------------
*  Firm-level sales outcome spec using Data Axle (RefUSA) sales volumes.
*
*  Goal:
*    - Treat sales as a new firm outcome and estimate the same interacted
*      remote×covid and remote×covid×startup effects used in firm_scaling.do,
*      with firm and year fixed effects, and optional IV via teleworkability.
*
*  REQUIRED INPUTS
*    - data/clean/firm_panel.dta, produced by:
*        src/stata/build_firm_panel.do
*    - data/clean/data_axle_sales_company_year.dta, produced by:
*        python src/py/build_data_axle_sales_extract.py
*
*  OUTPUTS
*    - results/raw/firm_sales/consolidated_results.csv
*====================================================================*

// Bootstrap paths -----------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

// Dependencies --------------------------------------------------------
capture which reghdfe
if _rc {
    di as error "Required package 'reghdfe' not found."
    di as error "Install once via:  ssc install reghdfe, replace"
    exit 199
}
capture which ivreghdfe
if _rc {
    di as error "Required package 'ivreghdfe' not found."
    di as error "Install once via:  ssc install ivreghdfe, replace"
    exit 199
}
capture which winsor2
if _rc {
    di as error "Required package 'winsor2' not found."
    di as error "Install once via:  ssc install winsor2, replace"
    exit 199
}

// Load panel ----------------------------------------------------------
use "$processed_data/firm_panel.dta", clear

// Build year-level panel ----------------------------------------------
capture confirm variable year
if _rc != 0 {
    capture confirm variable date
    if _rc == 0 {
        gen year = yofd(date)
    }
    else {
        capture confirm variable yh
        if _rc != 0 {
            di as error "firm_panel.dta missing year/date/yh; cannot align to annual Data Axle sales."
            exit 111
        }
        // `yh' is typically a Stata half-year date (%th). Convert via dofh().
        // If `yh' is a string like \"2019h2\", parse the year prefix.
        capture confirm string variable yh
        if _rc == 0 {
            gen year = real(substr(yh, 1, 4))
        }
        else {
            gen year = yofd(dofh(yh))
        }
    }
}

// Data Axle coverage (per PI email): 2017–2022
keep if inrange(year, 2017, 2022)

// Collapse half-year panel → firm-year (remote/startup/teleworkable are time-invariant)
collapse (mean) remote teleworkable startup ///
         (firstnm) firm_id, by(companyname year)

// Define covid at annual frequency and rebuild interactions (match build_firm_panel.do)
gen byte covid = (year >= 2020)
gen var3 = remote * covid
gen var4 = covid  * startup
gen var5 = remote * covid * startup
gen var6 = covid * teleworkable
gen var7 = startup * covid * teleworkable

// Merge Data Axle sales (companyname×year) ----------------------------
capture confirm file "$processed_data/data_axle_sales_company_year.dta"
if _rc != 0 {
    di as error "Missing $processed_data/data_axle_sales_company_year.dta."
    di as error "Run:"
    di as error "  python src/py/build_data_axle_sales_extract.py --data-axle-dir \"/path/to/Data Axle\""
    exit 601
}
merge 1:1 companyname year using "$processed_data/data_axle_sales_company_year.dta", keep(1 3)
tab _merge
// Restrict to firm-years with a Data Axle match (the outcome is missing otherwise).
keep if _merge == 3
drop _merge

// Match-quality diagnostics (for log / QA; not used as a filter in the baseline spec)
summarize n_rows n_city_match

// Outcomes -------------------------------------------------------------
// Notes / best practices:
//  - We use log(1 + sales) to handle zeros and heavy tails.
//  - We winsorize the log outcome at [1,99] to limit extreme influence.
//  - Parent sales includes a small number of sentinel top-coded values; set to missing.

// Top-coding / sentinel cleanup (parent sales):
replace parent_sales_max = . if parent_sales_max == 999999999

// Transformations (levels):
gen ln_sales_loc_max    = ln(sales_loc_max + 1) if !missing(sales_loc_max)
gen ln_parent_sales_max = ln(parent_sales_max + 1) if !missing(parent_sales_max)

// Winsorize transformed outcomes:
winsor2 ln_sales_loc_max ln_parent_sales_max, cuts(1 99) suffix(_we)

// Logging --------------------------------------------------------------
local specname "firm_sales"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

// Output dir ----------------------------------------------------------
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

// FE/cluster ----------------------------------------------------------
local FE "absorb(firm_id year) vce(cluster firm_id)"

// Loop over outcomes --------------------------------------------------
// Minimal set of sales outcomes (each runs on its own non-missing sample):
//  - Location sales (max): most robust to multi-row name matches.
//  - Parent sales (max): corporate-scale benchmark (more missing).
local outcome_vars ln_sales_loc_max_we ln_parent_sales_max_we

foreach y of local outcome_vars {
    di as text "→ Outcome: `y'"

    // Pre-COVID mean (reporting)
    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // Skip if outcome is entirely missing
    count if !missing(`y')
    if r(N) == 0 {
        di as error "  → Skipping `y' (all missing)."
        continue
    }

    // OLS -------------------------------------------------------------
    reghdfe `y' var3 var5 var4, `FE'
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

    // IV (2nd stage) --------------------------------------------------
    ivreghdfe `y' (var3 var5 = var6 var7) var4, `FE' savefirst
    local rkf = e(rkf)
    local N   = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
log close
