*============================================================*
* user_productivity_llm_equity_replace_startup_pair_fe.do
*
* Focused pair-FE analogue of the "replace startup with equity"
* user-productivity specification.
*
* Output:
*   results/raw/user_productivity_llm_equity_replace_startup_pair_fe_<panel>/consolidated_results.csv
*============================================================*

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

local specname "user_productivity_llm_equity_replace_startup_pair_fe_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile firm_keys llm_by_name signal_by_firm

* 1) Build firm_id x yh LLM signal panel
use "$processed_data/firm_panel.dta", clear
keep firm_id companyname yh
duplicates drop firm_id yh, force
gen str244 __firm_name_key = lower(trim(companyname))
gen str10  __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
save `firm_keys', replace

import delimited using "`llm_panel_csv'", clear varnames(1)
keep firm_id_key yh llm_n_parse_ok llm_equity_any
rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in llm_n_parse_ok llm_equity_any {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_name', replace

use `firm_keys', clear
merge 1:1 __firm_name_key __yh_key using `llm_by_name', keep(master match) nogen
keep firm_id yh llm_n_parse_ok llm_equity_any
duplicates drop firm_id yh, force
save `signal_by_firm', replace

* 2) Load user panel, merge signals, and backfill missing equity to zero
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `signal_by_firm', keep(master match)
drop _merge

foreach v in llm_n_parse_ok llm_equity_any {
    capture destring `v', replace force
}

gen double eq_any_obs = llm_equity_any
replace eq_any_obs = 0 if missing(eq_any_obs)
replace eq_any_obs = 0 if eq_any_obs < 0 | eq_any_obs > 1

bysort firm_id: egen double eq_any_firm = max(eq_any_obs)
replace eq_any_firm = 0 if missing(eq_any_firm)

gen double eq_any_firm_covid = eq_any_firm * covid
gen double var3_eq_any = var3 * eq_any_firm
gen double var6_eq_any = var6 * eq_any_firm

local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"
local y "total_contributions_q100"
local params "var3 var3_eq_any eq_any_firm_covid"

quietly count
local sample_n = r(N)
quietly summarize `y' if covid == 0, meanonly
local pre_mean = r(mean)

tempvar __tag_firm __tag_user
quietly egen `__tag_firm' = tag(firm_id)
quietly count if `__tag_firm' == 1
local n_firms = r(N)
quietly egen `__tag_user' = tag(user_id)
quietly count if `__tag_user' == 1
local n_users = r(N)

* 3) Output container
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str12 sample_mode ///
    str20 analysis_block ///
    str20 equity_measure ///
    str20 split_group ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs sample_n n_firms n_users ///
    using `out', replace

capture noisily reghdfe `y' var3 var3_eq_any eq_any_firm_covid, `FE'
if _rc {
    di as error "Regression failed: pair FE reduced1 OLS"
}
else {
    local nobs = e(N)
    foreach p of local params {
        capture local b = _b[`p']
        if _rc continue
        capture local se = _se[`p']
        if _rc continue
        local pval = .
        if (`se' == 0 | missing(`se')) {
            local b = .
            local se = .
        }
        else if `se' < . & e(df_r) < . {
            local t = `b' / `se'
            local pval = 2*ttail(e(df_r), abs(`t'))
        }
        post handle ("OLS") ("backfill") ("reduced1") ("any") ("all") ///
            ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
    }
}

capture noisily ivreghdfe `y' ///
    (var3 var3_eq_any = var6 var6_eq_any) ///
    eq_any_firm_covid, ///
    `FE'
if _rc {
    di as error "Regression failed: pair FE reduced1 IV"
}
else {
    local nobs = e(N)
    local rkf = .
    capture local rkf = e(rkf)
    foreach p of local params {
        capture local b = _b[`p']
        if _rc continue
        capture local se = _se[`p']
        if _rc continue
        local pval = .
        if (`se' == 0 | missing(`se')) {
            local b = .
            local se = .
        }
        else if `se' < . & e(df_r) < . {
            local t = `b' / `se'
            local pval = 2*ttail(e(df_r), abs(`t'))
        }
        post handle ("IV") ("backfill") ("reduced1") ("any") ("all") ///
            ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`nobs') (`sample_n') (`n_firms') (`n_users')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
capture log close
