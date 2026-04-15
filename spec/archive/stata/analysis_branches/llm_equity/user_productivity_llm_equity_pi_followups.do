*============================================================*
* user_productivity_llm_equity_pi_followups.do
*
* PI follow-up package for LLM equity measures:
*   1) Measure iterations:
*      - raw any/share/count
*      - strict-context any (DEI-noise reduced)
*      - software-only strict any
*      - discretized bins (median / top quartile / top quintile)
*   2) Matched vs backfill vs backfill+missing control
*   3) Backfill decomposition controls:
*      - no keyword hit
*      - keyword hit but unparsed
*
* Output:
*   results/raw/user_productivity_llm_equity_pi_followups_<panel>/consolidated_results.csv
*============================================================*

args panel_variant enriched_panel_csv
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

if "`enriched_panel_csv'" == "" local enriched_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv"

capture confirm file "`enriched_panel_csv'"
if _rc {
    di as error "Missing enriched LLM panel CSV: `enriched_panel_csv'"
    exit 601
}

local specname "user_productivity_llm_equity_pi_followups_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

* 1) Build user analysis panel + enriched firm-level signals
tempfile firm_keys llm_by_firm panel_all panel_mode

use "$processed_data/firm_panel.dta", clear
keep firm_id companyname yh
duplicates drop firm_id yh, force
gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
save `firm_keys', replace

import delimited using "`enriched_panel_csv'", clear varnames(1)
keep firm_id_key yh ///
    llm_n_parse_ok_raw ///
    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
    llm_equity_any_strict ///
    llm_equity_any_software_strict ///
    firm_raw_share_ge_median_obs firm_raw_share_top_quartile_obs firm_raw_share_top_quintile_obs ///
    firm_raw_count_ge_median_obs firm_raw_count_top_quartile_obs firm_raw_count_top_quintile_obs ///
    status_backfill_no_keyword_hit status_backfill_keyword_unparsed

rename firm_id_key __firm_name_key
rename yh __yh_key

foreach v in llm_n_parse_ok_raw ///
    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
    llm_equity_any_strict llm_equity_any_software_strict ///
    firm_raw_share_ge_median_obs firm_raw_share_top_quartile_obs firm_raw_share_top_quintile_obs ///
    firm_raw_count_ge_median_obs firm_raw_count_top_quartile_obs firm_raw_count_top_quintile_obs ///
    status_backfill_no_keyword_hit status_backfill_keyword_unparsed {
    capture destring `v', replace force
}

drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_firm', replace

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")

merge m:1 __firm_name_key __yh_key using `llm_by_firm', keep(master match) nogen

foreach v in llm_n_parse_ok_raw ///
    llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
    llm_equity_any_strict llm_equity_any_software_strict ///
    firm_raw_share_ge_median_obs firm_raw_share_top_quartile_obs firm_raw_share_top_quintile_obs ///
    firm_raw_count_ge_median_obs firm_raw_count_top_quartile_obs firm_raw_count_top_quintile_obs ///
    status_backfill_no_keyword_hit status_backfill_keyword_unparsed {
    capture destring `v', replace force
}

gen byte eq_has_parse = llm_n_parse_ok_raw > 0 if !missing(llm_n_parse_ok_raw)
replace eq_has_parse = 0 if missing(eq_has_parse)
replace status_backfill_no_keyword_hit = 0 if missing(status_backfill_no_keyword_hit)
replace status_backfill_keyword_unparsed = 0 if missing(status_backfill_keyword_unparsed)

save `panel_all', replace

* 2) Output container
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str20 sample_mode ///
    str40 analysis_block ///
    str32 equity_measure ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs sample_n n_firms n_users ///
    using `out', replace

local sample_modes "matched backfill backfill_missing backfill_decomp"
local outcomes "total_contributions_q100"
local measures "any_raw share_raw count_raw any_strict any_software_strict share_ge_median share_top_quartile share_top_quintile count_ge_median count_top_quartile count_top_quintile"

foreach sample_mode of local sample_modes {
    foreach measure of local measures {
        use `panel_all', clear

        if "`sample_mode'" == "matched" {
            keep if eq_has_parse == 1
        }

        quietly count
        local sample_n = r(N)
        if `sample_n' == 0 continue

        * Construct row-level equity series for this measure.
        gen double eq_obs = .

        if "`measure'" == "any_raw" {
            if "`sample_mode'" == "matched" replace eq_obs = llm_equity_any_raw if eq_has_parse == 1
            else replace eq_obs = cond(eq_has_parse == 1, llm_equity_any_raw, 0)
        }
        else if "`measure'" == "share_raw" {
            if "`sample_mode'" == "matched" replace eq_obs = llm_equity_share_parse_ok_raw if eq_has_parse == 1
            else replace eq_obs = cond(eq_has_parse == 1, llm_equity_share_parse_ok_raw, 0)
        }
        else if "`measure'" == "count_raw" {
            if "`sample_mode'" == "matched" replace eq_obs = llm_equity_count_parse_ok_raw if eq_has_parse == 1
            else replace eq_obs = cond(eq_has_parse == 1, llm_equity_count_parse_ok_raw, 0)
        }
        else if "`measure'" == "any_strict" {
            if "`sample_mode'" == "matched" replace eq_obs = llm_equity_any_strict if eq_has_parse == 1
            else replace eq_obs = cond(eq_has_parse == 1, llm_equity_any_strict, 0)
        }
        else if "`measure'" == "any_software_strict" {
            if "`sample_mode'" == "matched" replace eq_obs = llm_equity_any_software_strict if eq_has_parse == 1
            else replace eq_obs = cond(eq_has_parse == 1, llm_equity_any_software_strict, 0)
        }
        else if "`measure'" == "share_ge_median" {
            replace eq_obs = firm_raw_share_ge_median_obs
        }
        else if "`measure'" == "share_top_quartile" {
            replace eq_obs = firm_raw_share_top_quartile_obs
        }
        else if "`measure'" == "share_top_quintile" {
            replace eq_obs = firm_raw_share_top_quintile_obs
        }
        else if "`measure'" == "count_ge_median" {
            replace eq_obs = firm_raw_count_ge_median_obs
        }
        else if "`measure'" == "count_top_quartile" {
            replace eq_obs = firm_raw_count_top_quartile_obs
        }
        else if "`measure'" == "count_top_quintile" {
            replace eq_obs = firm_raw_count_top_quintile_obs
        }

        replace eq_obs = 0 if missing(eq_obs) & inlist("`sample_mode'", "backfill", "backfill_missing", "backfill_decomp")
        replace eq_obs = . if eq_obs < 0

        * Collapse row-level measure to firm-level exposure used in regressions.
        gen double eq_firm = .
        if inlist("`measure'", "share_raw", "count_raw") {
            bysort firm_id: egen double __eq_mean = mean(eq_obs)
            replace eq_firm = __eq_mean
            drop __eq_mean
        }
        else {
            bysort firm_id: egen double __eq_max = max(eq_obs)
            replace eq_firm = __eq_max
            drop __eq_max
        }
        replace eq_firm = 0 if missing(eq_firm) & inlist("`sample_mode'", "backfill", "backfill_missing", "backfill_decomp")

        bysort firm_id: egen double miss_parse_share_firm = mean(eq_has_parse == 0)
        bysort firm_id: egen double no_keyword_share_firm = mean(status_backfill_no_keyword_hit == 1)
        bysort firm_id: egen double unparsed_hit_share_firm = mean(status_backfill_keyword_unparsed == 1)

        gen double eq_firm_covid = eq_firm * covid
        gen double var3_eq = var3 * eq_firm
        gen double var5_eq = var5 * eq_firm
        gen double var6_eq = var6 * eq_firm
        gen double var7_eq = var7 * eq_firm

        gen double miss_parse_share_firm_covid = miss_parse_share_firm * covid
        gen double no_keyword_share_firm_covid = no_keyword_share_firm * covid
        gen double unparsed_hit_share_firm_covid = unparsed_hit_share_firm * covid

        local extra_controls ""
        local analysis_block "core_pooled"
        if "`sample_mode'" == "backfill_missing" {
            local extra_controls "miss_parse_share_firm_covid"
            local analysis_block "core_pooled_missing_ctrl"
        }
        else if "`sample_mode'" == "backfill_decomp" {
            local extra_controls "no_keyword_share_firm_covid unparsed_hit_share_firm_covid"
            local analysis_block "core_pooled_decomp_ctrl"
        }

        tempvar __tag_firm __tag_user
        quietly egen `__tag_firm' = tag(firm_id)
        quietly count if `__tag_firm' == 1
        local n_firms = r(N)
        quietly egen `__tag_user' = tag(user_id)
        quietly count if `__tag_user' == 1
        local n_users = r(N)

        foreach y of local outcomes {
            quietly summarize `y' if covid == 0, meanonly
            local pre_mean = r(mean)

            local params "var3 var5 var3_eq var5_eq"
            if "`sample_mode'" == "backfill_missing" {
                local params "`params' miss_parse_share_firm_covid"
            }
            else if "`sample_mode'" == "backfill_decomp" {
                local params "`params' no_keyword_share_firm_covid unparsed_hit_share_firm_covid"
            }

            capture noisily reghdfe `y' var3 var5 var3_eq var5_eq var4 eq_firm_covid `extra_controls', ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            if !_rc {
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
                        local pval = 2 * ttail(e(df_r), abs(`t'))
                    }
                    post handle ("OLS") ("`sample_mode'") ("`analysis_block'") ("`measure'") ///
                        ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean') ///
                        (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
                }
            }

            capture noisily ivreghdfe `y' ///
                (var3 var5 var3_eq var5_eq = var6 var7 var6_eq var7_eq) ///
                var4 eq_firm_covid `extra_controls', ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            if !_rc {
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
                        local pval = 2 * ttail(e(df_r), abs(`t'))
                    }
                    post handle ("IV") ("`sample_mode'") ("`analysis_block'") ("`measure'") ///
                        ("`y'") ("`p'") ///
                        (`b') (`se') (`pval') (`pre_mean') ///
                        (`rkf') (`nobs') (`sample_n') (`n_firms') (`n_users')
                }
            }
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV : `result_dir'/consolidated_results.csv"
capture log close
