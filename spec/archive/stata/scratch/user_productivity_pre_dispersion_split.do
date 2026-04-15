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



*-------------------------------------------------------------------------
*  user_productivity_pre_dispersion_split.do
*  — Split by pre-period (2019) dispersion of locations and rerun baseline
*    productivity regressions (OLS and IV) within each bucket.
*
*  Buckets: 2 (default), via quantiles of firm-level `filtered_msa_cnt`
*            from data/processed/company_dispersion_2019.csv merged into
*            the user panel by src/build_all_user_panels.do.
*
*  Baseline: mirrors spec/user_productivity.do (same outcome, FE, IV setup)
*
*  Usage examples:
*    do spec/user_productivity_pre_dispersion_split.do
*    do spec/user_productivity_pre_dispersion_split.do precovid 2
*
*-------------------------------------------------------------------------

* -------------------------------
* 0) Parse args and load panel
* -------------------------------
local nbins 2
args panel_variant nbins_arg
if "`panel_variant'" == "" local panel_variant "precovid"
if "`nbins_arg'"!="" local nbins `nbins_arg'

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

* Ensure the pre-period dispersion variables exist
capture confirm variable filtered_msa_cnt
if _rc {
    di as error "ERROR: filtered_msa_cnt not found in user panel."
    di as error "Make sure build_all_user_panels.do merged company_dispersion_2019.csv."
    exit 1
}

* ------------------------------------
* 1) Create 2-bin dispersion buckets
* ------------------------------------
* Use firm-level 2019 breadth (# MSAs) to split: lower vs higher dispersion
preserve
    keep firm_id filtered_msa_cnt
    duplicates drop firm_id, force
    xtile disp2_firm = filtered_msa_cnt, nq(`nbins')
    keep firm_id disp2_firm
    tempfile disp2
    save `disp2'
restore

merge m:1 firm_id using `disp2', nogenerate

* -------------------------------
* 2) Logging and output dirs
* -------------------------------
local specname "het_pre_dispersion_`panel_variant'_`nbins'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

* --------------------------------------
* 3) Postfiles (IV and OLS outputs)
* --------------------------------------
tempfile out_iv
capture postclose handle_iv
postfile handle_iv ///
    str8   bucket       ///  1, 2
    double coef3 se3 pval3   /// var3 stats
    double coef5 se5 pval5   /// var5 stats
    double rkf nobs avg_msa  /// FS F-stat, N, and avg 2019 MSAs per bin
    using `out_iv', replace

tempfile out_ols
capture postclose handle_ols
postfile handle_ols ///
    str8   bucket       ///  1, 2
    double coef3 se3 pval3   /// var3 stats
    double coef5 se5 pval5   /// var5 stats
    double rkf nobs avg_msa  /// placeholder (.) for rkf; include avg 2019 MSAs
    using `out_ols', replace

* --------------------------------------
* 4) Loop over buckets and run models
* --------------------------------------
local outcome total_contributions_q100

* --------------------------------------
* 3.5) Compute firm-weighted bin means (one per firm)
* --------------------------------------
preserve
    use "$processed_data/user_panel_`panel_variant'.dta", clear
    merge m:1 firm_id using `disp2', nogenerate
    keep firm_id disp2_firm filtered_msa_cnt
    duplicates drop firm_id, force
    forvalues g = 1/`nbins' {
        quietly summarize filtered_msa_cnt if disp2_firm == `g', meanonly
        local binmean`g' = r(mean)
    }
restore

forvalues g = 1/`nbins' {
    di as text "=== Pre-dispersion bucket `g' of `nbins' ==="

    * ----- IV (baseline, mirrors spec/user_productivity.do) -----
    ivreghdfe `outcome' ///
        (var3 var5 = var6 var7) var4 ///
        if disp2_firm == `g', ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst

    * Stats for var3 and var5
    local b3 = _b[var3]
    local s3 = _se[var3]
    local p3 = 2*ttail(e(df_r), abs(`b3'/`s3'))

    local b5 = _b[var5]
    local s5 = _se[var5]
    local p5 = 2*ttail(e(df_r), abs(`b5'/`s5'))

    post handle_iv ("`g'") ///
        (`b3') (`s3') (`p3') ///
        (`b5') (`s5') (`p5') ///
        (e(rkf)) (e(N)) (`binmean`g'')

    * ----- OLS (parallel to baseline) -----
    reghdfe `outcome' ///
        var3 var5 var4 ///
        if disp2_firm == `g', ///
        absorb(user_id firm_id yh) vce(cluster user_id)

    local b3o = _b[var3]
    local s3o = _se[var3]
    local p3o = 2*ttail(e(df_r), abs(`b3o'/`s3o'))

    local b5o = _b[var5]
    local s5o = _se[var5]
    local p5o = 2*ttail(e(df_r), abs(`b5o'/`s5o'))

    post handle_ols ("`g'") ///
        (`b3o') (`s3o') (`p3o') ///
        (`b5o') (`s5o') (`p5o') ///
        (.) (e(N)) (`binmean`g'')
}

* -------------------------------
* 5) Export results
* -------------------------------
postclose handle_iv
use `out_iv', clear
export delimited using "`result_dir'/var5_pre_dispersion_base.csv", replace

postclose handle_ols
use `out_ols', clear
export delimited using "`result_dir'/var5_pre_dispersion_base_ols.csv", replace

log close
di as result "→ IV CSV  : `result_dir'/var5_pre_dispersion_base.csv"
di as result "→ OLS CSV : `result_dir'/var5_pre_dispersion_base_ols.csv"
