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



* --------------------------------------------------------------------------
* User productivity: pairwise remote modality comparisons
* --------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname_base user_productivity_pairwise_`panel_variant'
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname_base'.log", replace text


local cwd = c(pwd)
if !regexm("`cwd'", "/spec$") {
    cd spec
}

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

// Ensure remote definition is available and consistent
drop if missing(remote)
local tol = 1e-06
capture drop remote_is_fr remote_is_ip remote_is_h
gen byte remote_is_fr = (remote >= 1-`tol')
replace remote_is_fr = 0 if missing(remote_is_fr)
replace remote_is_fr = 0 if remote > 1 + `tol'

gen byte remote_is_ip = (remote <= `tol')
replace remote_is_ip = 0 if missing(remote_is_ip)
replace remote_is_ip = 0 if remote < -`tol'

gen byte remote_is_h = (remote > `tol' & remote < 1-`tol')
replace remote_is_h = 0 if missing(remote_is_h)

// Persist base panel for reuse across comparisons
tempfile SOURCE
save `SOURCE'

local outcomes total_contributions_q100
local comparisons "fr_vs_ip hyb_vs_ip fr_vs_hyb"

foreach cmp of local comparisons {
    use `SOURCE', clear

    tempvar flag
    local result_suffix ""
    local treated_label ""
    if "`cmp'" == "fr_vs_ip" {
        keep if remote_is_fr | remote_is_ip
        gen byte `flag' = remote_is_fr
        local result_suffix "fr_vs_ip"
        local treated_label "Fully Remote vs In-Person"
    }
    else if "`cmp'" == "hyb_vs_ip" {
        keep if remote_is_h | remote_is_ip
        gen byte `flag' = remote_is_h
        local result_suffix "hyb_vs_ip"
        local treated_label "Hybrid vs In-Person"
    }
    else if "`cmp'" == "fr_vs_hyb" {
        keep if remote_is_fr | remote_is_h
        gen byte `flag' = remote_is_fr
        local result_suffix "fr_vs_hyb"
        local treated_label "Fully Remote vs Hybrid"
    }
    else {
        continue
    }

    count
    if r(N) == 0 {
        di as error "Comparison `cmp': empty sample, skipping"
        continue
    }

    count if `flag' == 1
    local treated_n = r(N)
    count if `flag' == 0
    local control_n = r(N)
    if (`treated_n' == 0 | `control_n' == 0) {
        di as error "Comparison `cmp': lacks treated or control units, skipping"
        continue
    }

    local v3n = "var3_`result_suffix'"
    local v5n = "var5_`result_suffix'"
    capture drop `v3n' `v5n'
    gen double `v3n' = `flag' * covid
    gen double `v5n' = `flag' * covid * startup
    local treat_var `v3n'
    local startup_var `v5n'

    di as text "-> `treated_label' :: using variables `treat_var' and `startup_var'"

    local result_dir "$results/`specname_base'_`result_suffix'"
    capture mkdir "`result_dir'"

    tempfile out
    capture postclose handle
    postfile handle ///
        str8   model_type ///
        str40  outcome   ///
        str40  param     ///
        double coef se pval pre_mean ///
        double rkf nobs ///
        using `out', replace

    foreach y of local outcomes {
        di as text "-> `treated_label' :: outcome `y'"

        summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        reghdfe `y' `treat_var' `startup_var' var4, absorb(user_id#firm_id yh) vce(cluster user_id)
        local N = e(N)
        foreach p in `treat_var' `startup_var' var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle ("OLS") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
        }

        ivreghdfe `y' (`treat_var' `startup_var' = var6 var7) var4, absorb(user_id#firm_id yh) vce(cluster user_id)
        local rkf = e(rkf)
        local N = e(N)
        foreach p in `treat_var' `startup_var' var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local pval = 2*ttail(e(df_r), abs(`b'/`se'))
            post handle ("IV") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
        }
    }

    postclose handle
    use `out', clear
    gen str20 comparison = "`result_suffix'"
    order comparison
    export delimited using "`result_dir'/consolidated_results.csv", replace
    di as result "-> CSV: `result_dir'/consolidated_results.csv"
}

log close
