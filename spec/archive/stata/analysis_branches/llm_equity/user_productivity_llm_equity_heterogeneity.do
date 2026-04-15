*============================================================*
* user_productivity_llm_equity_heterogeneity.do
* Core heterogeneity design for user_productivity (default: precovid):
*   1) pooled interaction model (equity-firm interactions)
*   2) split baseline model (equity firms vs non-equity firms)
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

local specname "user_productivity_llm_equity_heterogeneity_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile firm_keys llm_by_name llm_by_firm panel_ready

* 1) Map LLM equity signal onto firm_id × yh keys used by user panel
use "$processed_data/firm_panel.dta", clear
keep firm_id companyname yh
duplicates drop firm_id yh, force
gen str244 __firm_name_key = lower(trim(companyname))
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
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
save `llm_by_firm', replace

* 2) Build user panel with equity indicators
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `llm_by_firm', keep(master match)
drop _merge

* Backfill convention: treat any missing/unobserved equity signal as 0.
gen double eq_any_obs = llm_equity_any
replace eq_any_obs = 0 if missing(eq_any_obs)
replace eq_any_obs = 0 if eq_any_obs < 0 | eq_any_obs > 1

bysort firm_id: egen double eq_any_firm = max(eq_any_obs)
replace eq_any_firm = 0 if missing(eq_any_firm)
gen double eq_any_firm_covid = eq_any_firm * covid

gen double var3_eq_firm = var3 * eq_any_firm
gen double var5_eq_firm = var5 * eq_any_firm
gen double var6_eq_firm = var6 * eq_any_firm
gen double var7_eq_firm = var7 * eq_any_firm

save `panel_ready', replace

* 3) Results container
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str32  spec_variant ///
    str20  split_group ///
    str40  outcome ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs sample_n n_firms n_users ///
    using `out', replace

local outcomes total_contributions_q100
local pooled_params "var3 var5 var3_eq_firm var5_eq_firm eq_any_firm_covid"
local split_params "var3 var5"

foreach y of local outcomes {

    * ---- pooled interaction ----
    use `panel_ready', clear
    quietly count
    local sample_n = r(N)
    tempvar __tag_firm __tag_user
    quietly egen `__tag_firm' = tag(firm_id)
    quietly count if `__tag_firm' == 1
    local n_firms = r(N)
    quietly egen `__tag_user' = tag(user_id)
    quietly count if `__tag_user' == 1
    local n_users = r(N)
    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    capture quietly reghdfe `y' var3 var5 var3_eq_firm var5_eq_firm var4 eq_any_firm_covid, ///
        absorb(user_id firm_id yh) vce(cluster user_id)
    if !_rc {
        local nobs = e(N)
        foreach p of local pooled_params {
            capture local b = _b[`p']
            if _rc continue
            capture local se = _se[`p']
            if _rc continue
            local pval = .
            if `se' < . & `se' != 0 & e(df_r) < . {
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            post handle ("OLS") ("pooled_interaction") ("all") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
        }
    }

    capture quietly ivreghdfe `y' ///
        (var3 var5 var3_eq_firm var5_eq_firm = var6 var7 var6_eq_firm var7_eq_firm) ///
        var4 eq_any_firm_covid, ///
        absorb(user_id firm_id yh) vce(cluster user_id)
    if !_rc {
        local nobs = e(N)
        local rkf = .
        capture local rkf = e(rkf)
        foreach p of local pooled_params {
            capture local b = _b[`p']
            if _rc continue
            capture local se = _se[`p']
            if _rc continue
            local pval = .
            if `se' < . & `se' != 0 & e(df_r) < . {
                local t = `b'/`se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            post handle ("IV") ("pooled_interaction") ("all") ("`y'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`nobs') (`sample_n') (`n_firms') (`n_users')
        }
    }

    * ---- split baseline: non-equity vs equity firms ----
    foreach split in 0 1 {
        use `panel_ready', clear
        keep if eq_any_firm == `split'
        quietly count
        local sample_n = r(N)
        if `sample_n' == 0 continue

        tempvar __tag_firm_split __tag_user_split
        quietly egen `__tag_firm_split' = tag(firm_id)
        quietly count if `__tag_firm_split' == 1
        local n_firms = r(N)
        quietly egen `__tag_user_split' = tag(user_id)
        quietly count if `__tag_user_split' == 1
        local n_users = r(N)
        quietly summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)
        local split_group "equity_firm_`split'"

        capture quietly reghdfe `y' var3 var5 var4, absorb(user_id firm_id yh) vce(cluster user_id)
        if !_rc {
            local nobs = e(N)
            foreach p of local split_params {
                capture local b = _b[`p']
                if _rc continue
                capture local se = _se[`p']
                if _rc continue
                local pval = .
                if `se' < . & `se' != 0 & e(df_r) < . {
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                }
                post handle ("OLS") ("split_baseline") ("`split_group'") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }

        capture quietly ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if !_rc {
            local nobs = e(N)
            local rkf = .
            capture local rkf = e(rkf)
            foreach p of local split_params {
                capture local b = _b[`p']
                if _rc continue
                capture local se = _se[`p']
                if _rc continue
                local pval = .
                if `se' < . & `se' != 0 & e(df_r) < . {
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                }
                post handle ("IV") ("split_baseline") ("`split_group'") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV : `result_dir'/consolidated_results.csv"
capture log close
