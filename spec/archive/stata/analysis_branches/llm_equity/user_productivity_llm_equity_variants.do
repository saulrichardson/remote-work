args panel_variant llm_panel_csv
if "`panel_variant'" == "" local panel_variant "precovid"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

if "`llm_panel_csv'" == "" local llm_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity.csv"

capture confirm file "`llm_panel_csv'"
if _rc {
    di as error "Missing LLM panel CSV: `llm_panel_csv'"
    exit 601
}

local specname "user_productivity_llm_equity_variants_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile firm_keys llm_by_name llm_by_firm panel_ready

use "$processed_data/firm_panel.dta", clear
keep firm_id companyname yh
duplicates drop firm_id yh, force
gen str244 __firm_name_key = lower(trim(companyname))
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
save `firm_keys', replace

import delimited using "`llm_panel_csv'", clear varnames(1)
keep firm_id_key yh llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok
rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_name', replace

use `firm_keys', clear
merge 1:1 __firm_name_key __yh_key using `llm_by_name', keep(master match) nogen
keep firm_id yh llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok
duplicates drop firm_id yh, force
save `llm_by_firm', replace

use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `llm_by_firm', keep(master match)
drop _merge

* Backfill convention: treat any missing/unobserved equity fields as 0.
gen double eq_any_zero = llm_equity_any
gen double eq_share_zero = llm_equity_share_parse_ok

replace eq_any_zero = 0 if missing(eq_any_zero)
replace eq_share_zero = 0 if missing(eq_share_zero)

replace eq_any_zero = 0 if eq_any_zero < 0 | eq_any_zero > 1
replace eq_share_zero = 0 if eq_share_zero < 0 | eq_share_zero > 1

bysort firm_id: egen double eq_any_firm = max(eq_any_zero)
replace eq_any_firm = 0 if missing(eq_any_firm)
gen double eq_any_firm_covid = eq_any_firm * covid

gen double var3_eq_any = var3 * eq_any_zero
gen double var5_eq_any = var5 * eq_any_zero
gen double var6_eq_any = var6 * eq_any_zero
gen double var7_eq_any = var7 * eq_any_zero
gen double var3_eq_firm = var3 * eq_any_firm
gen double var5_eq_firm = var5 * eq_any_firm
gen double var6_eq_firm = var6 * eq_any_firm
gen double var7_eq_firm = var7 * eq_any_firm

save `panel_ready', replace

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8 model_type ///
    str32 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs sample_n ///
    using `out', replace

local outcomes total_contributions_q100
local spec_variants "baseline eq_any_zero eq_share_zero eq_any_interact_zero eq_any_firm_covid eq_any_firm_interact"

foreach spec_variant of local spec_variants {
    local sample_if "1"
    local ols_rhs "var3 var5 var4"
    local iv_endo "var3 var5"
    local iv_inst "var6 var7"
    local iv_exog "var4"
    local report_params "var3 var5 var4"

    if "`spec_variant'" == "eq_any_zero" {
        local ols_rhs "var3 var5 var4 eq_any_zero"
        local iv_exog "var4 eq_any_zero"
        local report_params "var3 var5 var4 eq_any_zero"
    }
    else if "`spec_variant'" == "eq_share_zero" {
        local ols_rhs "var3 var5 var4 eq_share_zero"
        local iv_exog "var4 eq_share_zero"
        local report_params "var3 var5 var4 eq_share_zero"
    }
    else if "`spec_variant'" == "eq_any_interact_zero" {
        local ols_rhs "var3 var5 var3_eq_any var5_eq_any var4 eq_any_zero"
        local iv_endo "var3 var5 var3_eq_any var5_eq_any"
        local iv_inst "var6 var7 var6_eq_any var7_eq_any"
        local iv_exog "var4 eq_any_zero"
        local report_params "var3 var5 var3_eq_any var5_eq_any var4 eq_any_zero"
    }
    else if "`spec_variant'" == "eq_any_firm_covid" {
        local ols_rhs "var3 var5 var4 eq_any_firm_covid"
        local iv_exog "var4 eq_any_firm_covid"
        local report_params "var3 var5 var4 eq_any_firm_covid"
    }
    else if "`spec_variant'" == "eq_any_firm_interact" {
        local ols_rhs "var3 var5 var3_eq_firm var5_eq_firm var4 eq_any_firm_covid"
        local iv_endo "var3 var5 var3_eq_firm var5_eq_firm"
        local iv_inst "var6 var7 var6_eq_firm var7_eq_firm"
        local iv_exog "var4 eq_any_firm_covid"
        local report_params "var3 var5 var3_eq_firm var5_eq_firm var4 eq_any_firm_covid"
    }

    foreach y of local outcomes {
        use `panel_ready', clear
        keep if `sample_if'
        quietly count
        local sample_n = r(N)
        if `sample_n' == 0 {
            continue
        }

        quietly summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        capture quietly reghdfe `y' `ols_rhs', absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc continue
        local nobs = e(N)
        foreach p of local report_params {
            capture local b = _b[`p']
            if _rc continue
            capture local se = _se[`p']
            if _rc continue
            local pval = .
            if `se' < . & `se' != 0 & e(df_r) < . {
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            post handle ("OLS") ("`spec_variant'") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`nobs') (`sample_n')
        }

        capture quietly ivreghdfe `y' (`iv_endo' = `iv_inst') `iv_exog', absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc continue
        local nobs = e(N)
        local rkf = .
        capture local rkf = e(rkf)
        foreach p of local report_params {
            capture local b = _b[`p']
            if _rc continue
            capture local se = _se[`p']
            if _rc continue
            local pval = .
            if `se' < . & `se' != 0 & e(df_r) < . {
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            post handle ("IV") ("`spec_variant'") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`nobs') (`sample_n')
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV : `result_dir'/consolidated_results.csv"
capture log close
