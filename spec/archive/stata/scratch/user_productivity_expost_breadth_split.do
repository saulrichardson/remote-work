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
*  user_productivity_expost_breadth_split.do
*  — Split baseline user productivity regressions by ex-post CBSA expansion
*    status (Δ breadth > 0 vs ≤ 0), mirroring the pre-dispersion split flow.
*
*  Source for split:
*    data/processed/firm_msa_delta.csv (built by py/build_firm_msa_delta.py)
*    - companyname_lower, delta_hc5r1, exp_hc5r1 (primary), delta_hc10r2, ...
*
*  Usage examples:
*    do spec/user_productivity_expost_breadth_split.do        // precovid
*    do spec/user_productivity_expost_breadth_split.do post   // post-only
*
*-------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

* Load user panel
use "$processed_data/user_panel_`panel_variant'.dta", clear

* Build merge key (use str# not strL for merge)
capture confirm variable companyname
if _rc {
    di as error "ERROR: user panel missing companyname"
    exit 198
}
gen str244 companyname_key = lower(substr(companyname,1,244))

* Bring in firm-level Δ breadth split (primary: exp_hc5r1)
preserve
    import delimited "$processed_data/firm_msa_delta.csv", clear varnames(1)
    keep companyname_lower exp_hc5r1 delta_hc5r1 delta_hc10r2
    gen str244 companyname_key = lower(substr(companyname_lower,1,244))
    drop companyname_lower
    tempfile delta
    save `delta'
restore

merge m:1 companyname_key using `delta', nogenerate

* Build two even user-level bins from firm Δ_hc5r1 on the estimation sample
preserve
    keep user_id delta_hc5r1 var3 var5 var4
    drop if missing(var3, var5, var4)
    keep user_id delta_hc5r1
    duplicates drop user_id, force
    xtile bin_user2 = delta_hc5r1, nq(2)
    tempfile ubins
    save `ubins'
restore

merge m:1 user_id using `ubins', nogenerate

capture confirm variable bin_user2
if _rc {
    di as error "ERROR: bin_user2 not constructed"
    exit 198
}

* Logging
local specname "user_prod_expost_breadth_split_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

* Postfiles
tempfile out_iv
capture postclose handle_iv
postfile handle_iv ///
    str8   bucket       ///  0,1
    double coef3 se3 pval3   /// var3
    double coef5 se5 pval5   /// var5
    double rkf nobs          /// first-stage rkF, N
    using `out_iv', replace

tempfile out_ols
capture postclose handle_ols
postfile handle_ols ///
    str8   bucket       ///  0,1
    double coef3 se3 pval3   /// var3
    double coef5 se5 pval5   /// var5
    double nobs              /// N
    using `out_ols', replace

local outcome total_contributions_q100

forvalues g = 1/2 {
    di as text "=== User-level Δ_hc5r1 bin `g' of 2 ==="

    * ----- IV (baseline spec) -----
    ivreghdfe `outcome' ///
        (var3 var5 = var6 var7) var4 ///
        if bin_user2 == `g', ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst

    local b3 = _b[var3]
    local s3 = _se[var3]
    local p3 = 2*ttail(e(df_r), abs(`b3'/`s3'))

    local b5 = _b[var5]
    local s5 = _se[var5]
    local p5 = 2*ttail(e(df_r), abs(`b5'/`s5'))

    post handle_iv ("`g'") (`b3') (`s3') (`p3') (`b5') (`s5') (`p5') (e(rkf)) (e(N))

    * ----- OLS -----
    reghdfe `outcome' var3 var5 var4 ///
        if bin_user2 == `g', ///
        absorb(user_id firm_id yh) vce(cluster user_id)

    local b3o = _b[var3]
    local s3o = _se[var3]
    local p3o = 2*ttail(e(df_r), abs(`b3o'/`s3o'))

    local b5o = _b[var5]
    local s5o = _se[var5]
    local p5o = 2*ttail(e(df_r), abs(`b5o'/`s5o'))

    post handle_ols ("`g'") (`b3o') (`s3o') (`p3o') (`b5o') (`s5o') (`p5o') (e(N))
}

* Export results
postclose handle_iv
use `out_iv', clear
export delimited using "`result_dir'/iv_by_expansion.csv", replace

postclose handle_ols
use `out_ols', clear
export delimited using "`result_dir'/ols_by_expansion.csv", replace

log close
di as result "→ IV CSV  : `result_dir'/iv_by_expansion.csv"
di as result "→ OLS CSV : `result_dir'/ols_by_expansion.csv"

exit
