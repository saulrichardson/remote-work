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
*  firm_msa_counts.do
*  — Baseline IV/OLS where outcome = number of MSAs (CBSAs)
*    Matches firm_scaling.do spec: firm & time FE, cluster by firm
*============================================================*

// 0) Setup environment
do "../globals.do"

// Setup logging
local specname "firm_msa_counts"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load firm panel (standard panel with treatment variables)
use "$processed_data/firm_panel.dta", clear

// 2) Merge firm×time geographic metrics that include CBSA counts
//    (Produced by py/build_geographic_expansion_metrics.py)
preserve
    import delimited "$processed_data/firm_geographic_expansion.csv", clear

    // Standardize firm name
    rename firm companyname
    replace companyname = lower(companyname)

    // Keep the variables we need, including total CBSA count per period
    keep companyname yh total_hires n_total_locations n_new_locations share_new_geo

    tempfile geo_metrics
    save `geo_metrics'
restore

// Standardize firm name in panel
replace companyname = lower(companyname)

// Merge
merge 1:1 companyname yh using `geo_metrics', keep(1 3) gen(geo_merge)

di _n "Merge results:"
tab geo_merge

// For CBSA counts, metrics are defined post-2019 by construction; restrict to observed periods
keep if geo_merge == 3

// 3) Define outcomes: number of MSAs and its log for scale robustness
gen n_msas = n_total_locations
label var n_msas "# of CBSAs with hires (firm×yh)"

gen log_n_msas = log(n_msas + 1)
label var log_n_msas "log(1 + # of CBSAs)"

// Quick sanity checks
sum n_msas log_n_msas if covid == 1

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

// First-stage file
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

// 5) Baseline regressions (OLS and IV), firm & time FE, cluster by firm
local outcomes n_msas log_n_msas

foreach y of local outcomes {
    di _n "→ Processing outcome: `y'"

    // Variation check
    qui sum `y' if !missing(var3, var5, var4)
    if r(N) == 0 | r(sd) == 0 {
        di "  Skipping `y' - insufficient variation"
        continue
    }

    // Pre-period mean (not used analytically here; just for consistency)
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

    // --- IV (2SLS) ---
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

    // --- First-stage diagnostics (record once for n_msas) ---
    if "`y'" == "n_msas" {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        // var3 first stage
        qui estimates restore _ivreg2_var3
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

        // var5 first stage
        qui estimates restore _ivreg2_var5
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
di "FIRM MSA COUNT ANALYSIS COMPLETE"
di "Results saved to: `result_dir'"
di "========================================"

log close
exit

