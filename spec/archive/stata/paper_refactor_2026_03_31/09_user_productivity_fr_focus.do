* --------------------------------------------------------------------------
* User productivity: fully-remote focused modality comparisons
* --------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local specname_base user_productivity_fr_focus_`panel_variant'

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname_base'.log", replace text



use "$processed_data/user_panel_`panel_variant'.dta", clear

drop if missing(remote)


capture drop fr hyb ip nonfr

// Fully remote indicator based on exact 100% remote share
gen byte fr = (remote == 1)
replace fr = 0 if missing(fr)

// In-person (exactly zero remote exposure)
gen byte ip = (remote == 0)
replace ip = 0 if missing(ip)

// Hybrid (anything strictly between the extremes)
gen byte hyb = (remote > 0 & remote < 1)
replace hyb = 0 if missing(hyb)

// Everyone who is not fully remote (hybrid or in-person)
gen byte nonfr = hyb | ip
replace nonfr = 0 if missing(nonfr)

tempfile SOURCE
save `SOURCE'

local fe_configs "match regular"
local fe_absorb_match   "firm_id#user_id yh"
local fe_absorb_regular "user_id firm_id yh"

local outcomes total_contributions_q100
local comparisons "fr_vs_hyb fr_vs_all"

foreach cmp of local comparisons {
    use `SOURCE', clear

    tempvar flag
    local result_suffix ""
    local treated_label ""
    local comparison_group ""

    if "`cmp'" == "fr_vs_all" {
        keep if fr | hyb | ip
        gen byte `flag' = fr
        local result_suffix "fr_vs_all"
        local treated_label "Fully Remote vs Everyone Else"
        local comparison_group "Hybrid/In-Person"
    }
    else if "`cmp'" == "fr_vs_hyb" {
        keep if fr | hyb
        gen byte `flag' = fr
        local result_suffix "fr_vs_hyb"
        local treated_label "Fully Remote vs Hybrid"
        local comparison_group "Hybrid"
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
        str20  comparison ///
        str24  comparison_group ///
        str12  fe_tag ///
        using `out', replace

    foreach fe of local fe_configs {
        local absorb = "`fe_absorb_`fe''"

        foreach y of local outcomes {
            di as text "-> `treated_label' [`fe'] :: outcome `y'"

            summarize `y' if covid == 0, meanonly
            local pre_mean = r(mean)

            reghdfe `y' `treat_var' `startup_var' var4, absorb(`absorb') vce(cluster user_id)
            local N = e(N)
            foreach p in `treat_var' `startup_var' var4 {
                local b    = _b[`p']
                local se   = _se[`p']
                local pval = 2*ttail(e(df_r), abs(`b'/`se'))
                post handle ("OLS") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N') ("`result_suffix'") ("`comparison_group'") ("`fe'")
            }

            ivreghdfe `y' (`treat_var' `startup_var' = var6 var7) var4, absorb(`absorb') vce(cluster user_id)
            local rkf = e(rkf)
            local N = e(N)
            foreach p in `treat_var' `startup_var' var4 {
                local b    = _b[`p']
                local se   = _se[`p']
                local pval = 2*ttail(e(df_r), abs(`b'/`se'))
                post handle ("IV") ("`y'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N') ("`result_suffix'") ("`comparison_group'") ("`fe'")
            }
        }
    }

    postclose handle
    use `out', clear
    order comparison comparison_group fe_tag
    export delimited using "`result_dir'/consolidated_results.csv", replace
    di as result "-> CSV: `result_dir'/consolidated_results.csv"
}

log close
