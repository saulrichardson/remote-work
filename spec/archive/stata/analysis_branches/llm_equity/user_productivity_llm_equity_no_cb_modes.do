*============================================================*
* user_productivity_llm_equity_no_cb_modes.do
*
* LLM equity analysis for user productivity using the BACKFILL convention only:
*   - Full user panel (merged with firm×half-year LLM signals)
*   - Missing / unobserved LLM equity fields are coded as 0
*
* Output:
*   - results/raw/user_productivity_llm_equity_no_cb_modes_<panel>/consolidated_results.csv
*============================================================*

args panel_variant llm_panel_csv
if "`panel_variant'" == "" local panel_variant "precovid"

* 0) Setup environment
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

local specname "user_productivity_llm_equity_no_cb_modes_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

* 1) Build firm_id × yh signal panel for LLM
tempfile firm_keys llm_by_name signal_by_firm panel_mode

use "$processed_data/firm_panel.dta", clear
keep firm_id companyname yh
duplicates drop firm_id yh, force
gen str244 __firm_name_key = lower(trim(companyname))
gen str10  __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
save `firm_keys', replace

import delimited using "`llm_panel_csv'", clear varnames(1)
keep firm_id_key yh llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok llm_n_equity_true
rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok llm_n_equity_true {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_name', replace

use `firm_keys', clear
merge 1:1 __firm_name_key __yh_key using `llm_by_name', keep(master match) nogen
keep firm_id yh llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok llm_n_equity_true
duplicates drop firm_id yh, force
save `signal_by_firm', replace

* 2) Load user panel and merge LLM signals
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `signal_by_firm', keep(master match)
drop _merge

foreach v in llm_n_parse_ok llm_equity_any llm_equity_share_parse_ok llm_n_equity_true {
    capture destring `v', replace force
}

gen byte eq_has_parse = llm_n_parse_ok > 0 if !missing(llm_n_parse_ok)
replace eq_has_parse = 0 if missing(eq_has_parse)

* 3) Output containers
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

	local sample_modes "backfill"
	local outcomes "total_contributions_q100"

	foreach sample_mode of local sample_modes {
	    preserve

	    quietly count
	    if r(N) == 0 {
	        di as error "No rows in sample_mode=`sample_mode' after sample restrictions."
	        restore
	        continue
	    }

	    * Backfill coding: treat anything unobserved as 0.
	    gen double eq_any_obs = llm_equity_any
	    gen double eq_share_obs = llm_equity_share_parse_ok
	    gen double eq_count_obs = llm_n_equity_true

	    replace eq_any_obs = 0 if missing(eq_any_obs)
	    replace eq_share_obs = 0 if missing(eq_share_obs)
	    replace eq_count_obs = 0 if missing(eq_count_obs)

	    replace eq_any_obs = 0 if eq_any_obs < 0 | eq_any_obs > 1
	    replace eq_share_obs = 0 if eq_share_obs < 0 | eq_share_obs > 1
	    replace eq_count_obs = 0 if eq_count_obs < 0

	    bysort firm_id: egen double eq_any_firm = max(eq_any_obs)
	    replace eq_any_firm = 0 if missing(eq_any_firm)

    bysort firm_id: egen double eq_share_firm = mean(eq_share_obs)
    replace eq_share_firm = 0 if missing(eq_share_firm)

    bysort firm_id: egen double eq_count_mean_firm = mean(eq_count_obs)
    replace eq_count_mean_firm = 0 if missing(eq_count_mean_firm)

    gen double eq_any_firm_covid = eq_any_firm * covid
    gen double eq_share_firm_covid = eq_share_firm * covid
    gen double eq_count_mean_firm_covid = eq_count_mean_firm * covid

    gen double var3_eq_any = var3 * eq_any_firm
    gen double var5_eq_any = var5 * eq_any_firm
    gen double var6_eq_any = var6 * eq_any_firm
    gen double var7_eq_any = var7 * eq_any_firm

    gen double var3_eq_share = var3 * eq_share_firm
    gen double var5_eq_share = var5 * eq_share_firm
    gen double var6_eq_share = var6 * eq_share_firm
    gen double var7_eq_share = var7 * eq_share_firm

    gen double var3_eq_count_mean = var3 * eq_count_mean_firm
    gen double var5_eq_count_mean = var5 * eq_count_mean_firm
    gen double var6_eq_count_mean = var6 * eq_count_mean_firm
    gen double var7_eq_count_mean = var7 * eq_count_mean_firm

    save `panel_mode', replace

    foreach y of local outcomes {
        use `panel_mode', clear
        quietly count
        local sample_n = r(N)
        if `sample_n' == 0 continue

        tempvar __tag_firm __tag_user
        quietly egen `__tag_firm' = tag(firm_id)
        quietly count if `__tag_firm' == 1
        local n_firms = r(N)
        quietly egen `__tag_user' = tag(user_id)
        quietly count if `__tag_user' == 1
        local n_users = r(N)
        quietly summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)

        * Core pooled (extensive / any)
        local params_any "var3 var5 var3_eq_any var5_eq_any eq_any_firm_covid"

        capture noisily reghdfe `y' var3 var5 var3_eq_any var5_eq_any var4 eq_any_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=core_pooled model=OLS outcome=`y'"
        }
        else {
            local nobs = e(N)
            foreach p of local params_any {
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
                post handle ("OLS") ("`sample_mode'") ("core_pooled") ("any") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }

        capture noisily ivreghdfe `y' ///
            (var3 var5 var3_eq_any var5_eq_any = var6 var7 var6_eq_any var7_eq_any) ///
            var4 eq_any_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=core_pooled model=IV outcome=`y'"
        }
        else {
            local nobs = e(N)
            local rkf = .
            capture local rkf = e(rkf)
            foreach p of local params_any {
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
                post handle ("IV") ("`sample_mode'") ("core_pooled") ("any") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }

        * Core split baseline by extensive equity indicator
        local split_params "var3 var5"
        foreach split in 0 1 {
            use `panel_mode', clear
            keep if eq_any_firm == `split'
            quietly count
            local sample_n_split = r(N)
            if `sample_n_split' == 0 continue

            tempvar __tag_firm_split __tag_user_split
            quietly egen `__tag_firm_split' = tag(firm_id)
            quietly count if `__tag_firm_split' == 1
            local n_firms_split = r(N)
            quietly egen `__tag_user_split' = tag(user_id)
            quietly count if `__tag_user_split' == 1
            local n_users_split = r(N)
            quietly summarize `y' if covid == 0, meanonly
            local pre_mean_split = r(mean)
            local split_group "eq_any_firm_`split'"

            capture noisily reghdfe `y' var3 var5 var4, absorb(user_id firm_id yh) vce(cluster user_id)
            if _rc {
                di as error "Regression failed: mode=`sample_mode' block=core_split model=OLS split=`split' outcome=`y'"
            }
            else {
                local nobs = e(N)
                foreach p of local split_params {
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
                    post handle ("OLS") ("`sample_mode'") ("core_split") ("any") ("`split_group'") ///
                        ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean_split') ///
                        (.) (`nobs') (`sample_n_split') (`n_firms_split') (`n_users_split')
                }
            }

            capture noisily ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            if _rc {
                di as error "Regression failed: mode=`sample_mode' block=core_split model=IV split=`split' outcome=`y'"
            }
            else {
                local nobs = e(N)
                local rkf = .
                capture local rkf = e(rkf)
                foreach p of local split_params {
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
                    post handle ("IV") ("`sample_mode'") ("core_split") ("any") ("`split_group'") ///
                        ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean_split') ///
                        (`rkf') (`nobs') (`sample_n_split') (`n_firms_split') (`n_users_split')
                }
            }
        }

        * Intensive pooled (share)
        use `panel_mode', clear
        local params_share "var3 var5 var3_eq_share var5_eq_share eq_share_firm_covid"

        capture noisily reghdfe `y' var3 var5 var3_eq_share var5_eq_share var4 eq_share_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=intensive_share model=OLS outcome=`y'"
        }
        else {
            local nobs = e(N)
            foreach p of local params_share {
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
                post handle ("OLS") ("`sample_mode'") ("intensive_share") ("share") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }

        capture noisily ivreghdfe `y' ///
            (var3 var5 var3_eq_share var5_eq_share = var6 var7 var6_eq_share var7_eq_share) ///
            var4 eq_share_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=intensive_share model=IV outcome=`y'"
        }
        else {
            local rkf = .
            capture local rkf = e(rkf)
            foreach p of local params_share {
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
                post handle ("IV") ("`sample_mode'") ("intensive_share") ("share") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (e(N)) (`sample_n') (`n_firms') (`n_users')
            }
        }

        * Intensive pooled (count mean)
        use `panel_mode', clear
        local params_count "var3 var5 var3_eq_count_mean var5_eq_count_mean eq_count_mean_firm_covid"

        capture noisily reghdfe `y' var3 var5 var3_eq_count_mean var5_eq_count_mean var4 eq_count_mean_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=intensive_count model=OLS outcome=`y'"
        }
        else {
            local nobs = e(N)
            foreach p of local params_count {
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
                post handle ("OLS") ("`sample_mode'") ("intensive_count") ("count_mean") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }

        capture noisily ivreghdfe `y' ///
            (var3 var5 var3_eq_count_mean var5_eq_count_mean = var6 var7 var6_eq_count_mean var7_eq_count_mean) ///
            var4 eq_count_mean_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=intensive_count model=IV outcome=`y'"
        }
        else {
            local rkf = .
            capture local rkf = e(rkf)
            foreach p of local params_count {
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
                post handle ("IV") ("`sample_mode'") ("intensive_count") ("count_mean") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (e(N)) (`sample_n') (`n_firms') (`n_users')
            }
        }

        * Reduced-1: Remote DD + equity heterogeneity (no startup interaction layer)
        use `panel_mode', clear
        local params_reduced1 "var3 var3_eq_any eq_any_firm_covid"

        capture noisily reghdfe `y' var3 var3_eq_any eq_any_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=reduced1 model=OLS outcome=`y'"
        }
	        else {
	            foreach p of local params_reduced1 {
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
                post handle ("OLS") ("`sample_mode'") ("reduced1") ("any") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (e(N)) (`sample_n') (`n_firms') (`n_users')
            }
        }

        capture noisily ivreghdfe `y' ///
            (var3 var3_eq_any = var6 var6_eq_any) ///
            eq_any_firm_covid, ///
            absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=reduced1 model=IV outcome=`y'"
        }
	        else {
	            local rkf = .
	            capture local rkf = e(rkf)
	            foreach p of local params_reduced1 {
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
                post handle ("IV") ("`sample_mode'") ("reduced1") ("any") ("all") ///
                    ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (e(N)) (`sample_n') (`n_firms') (`n_users')
            }
        }

        * Reduced-2: Remote × Post only DD (no equity interactions)
        use `panel_mode', clear
        capture noisily reghdfe `y' var3, absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=reduced2 model=OLS outcome=`y'"
        }
        else {
            local b = _b[var3]
            local se = _se[var3]
            local pval = .
            if (`se' == 0 | missing(`se')) {
                local b = .
                local se = .
            }
            else if `se' < . & e(df_r) < . {
                local t = `b' / `se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            post handle ("OLS") ("`sample_mode'") ("reduced2") ("any") ("all") ///
                ("`y'") ("var3") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (e(N)) (`sample_n') (`n_firms') (`n_users')
        }

        capture noisily ivreghdfe `y' (var3 = var6), absorb(user_id firm_id yh) vce(cluster user_id)
        if _rc {
            di as error "Regression failed: mode=`sample_mode' block=reduced2 model=IV outcome=`y'"
        }
        else {
            local b = _b[var3]
            local se = _se[var3]
            local pval = .
            if (`se' == 0 | missing(`se')) {
                local b = .
                local se = .
            }
            else if `se' < . & e(df_r) < . {
                local t = `b' / `se'
                local pval = 2*ttail(e(df_r), abs(`t'))
            }
            local rkf = .
            capture local rkf = e(rkf)
            post handle ("IV") ("`sample_mode'") ("reduced2") ("any") ("all") ///
                ("`y'") ("var3") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (e(N)) (`sample_n') (`n_firms') (`n_users')
        }

        * Concentration OLS: Equity exposure × Post (no remote regressor)
        use `panel_mode', clear
        foreach m in any share count_mean {
            local mvar "eq_`m'_firm_covid"
            capture noisily reghdfe `y' `mvar', absorb(user_id firm_id yh) vce(cluster user_id)
            if _rc {
                di as error "Regression failed: mode=`sample_mode' block=concentration measure=`m' outcome=`y'"
            }
            else {
                local b = _b[`mvar']
                local se = _se[`mvar']
                local pval = .
                if (`se' == 0 | missing(`se')) {
                    local b = .
                    local se = .
                }
                else if `se' < . & e(df_r) < . {
                    local t = `b' / `se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                }
                post handle ("OLS") ("`sample_mode'") ("concentration") ("`m'") ("all") ///
                    ("`y'") ("`mvar'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (e(N)) (`sample_n') (`n_firms') (`n_users')
            }
        }
    }

    restore
}

* 4) Export
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ Regression CSV: `result_dir'/consolidated_results.csv"
capture log close
