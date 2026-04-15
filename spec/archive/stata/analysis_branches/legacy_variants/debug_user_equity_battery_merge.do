*============================================================*
* debug_user_equity_battery_merge.do
*
* Purpose:
*   Sanity-check that the enriched firm×yh equity panel actually merges onto
*   the user panel (and produces non-zero variation) under the battery
*   backfill=0 convention.
*
* Usage:
*   ./bin/stata -b do spec/stata/debug_user_equity_battery_merge.do precovid [enriched_panel_csv]
*============================================================*

args panel_variant enriched_panel_csv
if "`panel_variant'" == "" local panel_variant "precovid"

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
    di as error "Missing enriched LLM equity panel: `enriched_panel_csv'"
    exit 601
}

local specname "debug_user_equity_battery_merge_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile llm_by_firm

preserve
    import delimited using "`enriched_panel_csv'", clear varnames(1)
    keep firm_id_key yh ///
        llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
        llm_equity_any_strict llm_equity_share_parse_ok_strict llm_equity_count_parse_ok_strict ///
        llm_equity_any_software_strict ///
        n_llm_target_postings llm_n_parse_ok_raw llm_n_equity_true_raw llm_n_equity_true_strict ///
        n_postings_desc_total n_keyword_hit_candidates

    rename firm_id_key __firm_name_key
    rename yh __yh_key
    replace __firm_name_key = lower(trim(__firm_name_key))
    replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
    foreach v in ///
        llm_equity_any_raw llm_equity_share_parse_ok_raw llm_equity_count_parse_ok_raw ///
        llm_equity_any_strict llm_equity_share_parse_ok_strict llm_equity_count_parse_ok_strict ///
        llm_equity_any_software_strict ///
        n_llm_target_postings llm_n_parse_ok_raw llm_n_equity_true_raw llm_n_equity_true_strict ///
        n_postings_desc_total n_keyword_hit_candidates {
        capture destring `v', replace force
        replace `v' = 0 if missing(`v')
    }

    drop if missing(__firm_name_key) | missing(__yh_key)
    duplicates drop __firm_name_key __yh_key, force
    save `llm_by_firm', replace
restore

use "$processed_data/user_panel_`panel_variant'.dta", clear
gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")

capture drop _merge
merge m:1 __firm_name_key __yh_key using `llm_by_firm'

di as text "Merge table (_merge):"
tab _merge

foreach v in ///
    llm_equity_any_raw llm_equity_any_strict llm_equity_any_software_strict ///
    llm_equity_share_parse_ok_raw llm_equity_share_parse_ok_strict ///
    llm_equity_count_parse_ok_raw llm_equity_count_parse_ok_strict ///
    n_keyword_hit_candidates n_postings_desc_total n_llm_target_postings llm_n_parse_ok_raw ///
    llm_n_equity_true_raw llm_n_equity_true_strict {

    capture confirm variable `v'
    if !_rc {
        replace `v' = 0 if missing(`v')
        quietly summarize `v'
        di as text "`v'  mean=" %9.4f r(mean) "  sd=" %9.4f r(sd) "  min=" %9.4f r(min) "  max=" %9.4f r(max)
        quietly count if `v' > 0
        di as text "   n(`v'>0)=" %12.0fc r(N)
    }
}

log close
