*====================================================================*
*  spec/user_mechanisms_keep_remote.do
*  ------------------------------------------------------------------
*  Pair-FE worker-level mechanisms table where competing channels
*  enter on the remote margin rather than as plain post-period controls.
*
*  Columns mirror the paper's mechanisms sequence:
*      (1) Firm growth
*      (2) Baseline
*      (3) Equity compensation
*      (4) Firm growth + equity compensation
*      (5) HHI
*      (6) Seniority
*      (7) HHI + Seniority
*
*  Equity support rule:
*      - postings but no keyword hit => zero
*      - keyword hit but no parse-successful LLM output => excluded
*      - no postings coverage => excluded
*
*  Fixed effects: worker-firm pair + half-year
*      absorb(firm_id#user_id yh), cluster(user_id)
*====================================================================*

args panel_variant enriched_panel_csv
if "`panel_variant'" == "" local panel_variant "precovid"

local specname   "05_user_mechanisms_keep_remote_`panel_variant'"

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
log using "$LOG_DIR/`specname'.log", replace text

if "`enriched_panel_csv'" == "" local enriched_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv"
capture confirm file "`enriched_panel_csv'"
if _rc {
    di as error "Missing enriched LLM equity panel: `enriched_panel_csv'"
    exit 601
}

local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

tempfile llm_by_firm panel_plain panel_growth_endog g_postavg

* Load user panel ------------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

local FE   "absorb(firm_id#user_id yh) vce(cluster user_id)"

* Core mechanism variables --------------------------------------------
gen seniority_4 = !inrange(seniority_levels, 1, 3)

gen var11 = covid*hhi_1000
gen var14 = covid*seniority_4

gen hr_hhi_remote = var3*hhi_1000
gen hr_hhi_inst   = var6*hhi_1000

gen hr_sen_remote = var3*seniority_4
gen hr_sen_inst   = var6*seniority_4

* Equity mechanism path -----------------------------------------------
preserve
    import delimited using "`enriched_panel_csv'", clear varnames(1)
    keep firm_id_key yh n_postings_desc_total n_keyword_hit_candidates llm_n_parse_ok_raw llm_equity_any_strict
    rename firm_id_key __firm_name_key
    rename yh __yh_key
    replace __firm_name_key = lower(trim(__firm_name_key))
    replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
    foreach v in n_postings_desc_total n_keyword_hit_candidates llm_n_parse_ok_raw llm_equity_any_strict {
        capture destring `v', replace force
    }
    drop if missing(__firm_name_key) | missing(__yh_key)
    duplicates drop __firm_name_key __yh_key, force
    save `llm_by_firm', replace
restore

gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")

merge m:1 __firm_name_key __yh_key using `llm_by_firm', keep(master match) nogen

foreach v in n_postings_desc_total n_keyword_hit_candidates llm_n_parse_ok_raw llm_equity_any_strict {
    capture destring `v', replace force
}

gen byte eq_row_has_postings = n_postings_desc_total > 0 if !missing(n_postings_desc_total)
replace eq_row_has_postings = 0 if missing(eq_row_has_postings)

gen byte eq_row_keyword_hit = n_keyword_hit_candidates > 0 if !missing(n_keyword_hit_candidates)
replace eq_row_keyword_hit = 0 if missing(eq_row_keyword_hit)

gen byte eq_row_parse_ok = llm_n_parse_ok_raw > 0 if !missing(llm_n_parse_ok_raw)
replace eq_row_parse_ok = 0 if missing(eq_row_parse_ok)

gen byte eq_row_equity_pos = eq_row_parse_ok == 1 & llm_equity_any_strict == 1
replace eq_row_equity_pos = 0 if missing(eq_row_equity_pos)

bysort firm_id: egen byte eq_firm_has_postings = max(eq_row_has_postings)
bysort firm_id: egen byte eq_firm_keyword_hit = max(eq_row_keyword_hit)
bysort firm_id: egen byte eq_firm_parse_ok = max(eq_row_parse_ok)
bysort firm_id: egen double eq_any_firm = max(eq_row_equity_pos)
replace eq_any_firm = 0 if missing(eq_any_firm)

gen byte eq_firm_keyword_unparsed = eq_firm_keyword_hit == 1 & eq_firm_parse_ok == 0
gen byte eq_main_sample = eq_firm_has_postings == 1 & eq_firm_keyword_unparsed == 0

bysort firm_id: gen byte __firm_first = _n == 1
quietly count if __firm_first & eq_firm_keyword_hit == 1 & eq_firm_parse_ok == 1
local n_firms_keyword_parse = r(N)
quietly count if __firm_first & eq_firm_has_postings == 1 & eq_firm_keyword_hit == 0
local n_firms_postings_no_keyword = r(N)
quietly count if __firm_first & eq_firm_keyword_unparsed == 1
local n_firms_keyword_unparsed = r(N)
quietly count if __firm_first & eq_firm_has_postings == 0
local n_firms_no_postings = r(N)

di as text "Equity coverage buckets:"
di as text "  Firms with keyword hit and parse-successful LLM output: `n_firms_keyword_parse'"
di as text "  Firms with postings but no keyword hit:                `n_firms_postings_no_keyword'"
di as text "  Firms with keyword hit but no parse-successful output: `n_firms_keyword_unparsed'"
di as text "  Firms with no postings coverage:                       `n_firms_no_postings'"

gen hr_eq_post   = covid*eq_any_firm
gen hr_eq_remote = var3*eq_any_firm
gen hr_eq_inst   = var6*eq_any_firm

save `panel_plain', replace

summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

* Firm-growth mechanism path ------------------------------------------
preserve
    use "$processed_data/firm_panel.dta", clear
    capture confirm variable growth_rate_we
    if _rc {
        di as error "Missing growth_rate_we in $processed_data/firm_panel.dta"
        exit 459
    }
    capture confirm variable covid
    if _rc {
        di as error "Missing covid in $processed_data/firm_panel.dta"
        exit 459
    }
    keep companyname growth_rate_we covid
    keep if covid == 1
    collapse (mean) growth_rate_we, by(companyname)
    rename growth_rate_we growth_rate_we_post_c
    xtile tile_post_c = growth_rate_we_post_c, nq(2)
    save `g_postavg', replace
restore

use `panel_plain', clear
merge m:1 companyname using `g_postavg', keep(match) nogen
gen hr_growth_post   = covid*tile_post_c
gen hr_growth_remote = var3*tile_post_c
gen hr_growth_inst   = var6*tile_post_c
save `panel_growth_endog', replace

* Results postfile -----------------------------------------------------
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  ///
    str244 spec        ///
    str40  param       ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

* Spec definitions -----------------------------------------------------
local specs ///
  baseline ///
  growth_endog ///
  equity ///
  growth_endog_equity ///
  hhi ///
  seniority ///
  hhi_seniority

local report_params "var3 var5"

foreach s in `specs' {
    di as text "→ Spec: `s'"

    if inlist("`s'", "growth_endog", "growth_endog_equity") {
        use `panel_growth_endog', clear
    }
    else {
        use `panel_plain', clear
    }

    if inlist("`s'", "equity", "growth_endog_equity") {
        keep if eq_main_sample == 1
    }

    if "`s'" == "baseline" {
        local OLS_RHS  "var3 var5 var4"
        local IV_ENDO  "var3 var5"
        local IV_INSTR "var6 var7"
        local IV_EXOG  "var4"
    }
    else if "`s'" == "growth_endog" {
        local OLS_RHS  "var3 var5 hr_growth_remote var4 hr_growth_post"
        local IV_ENDO  "var3 var5 hr_growth_remote"
        local IV_INSTR "var6 var7 hr_growth_inst"
        local IV_EXOG  "var4 hr_growth_post"
    }
    else if "`s'" == "equity" {
        local OLS_RHS  "var3 var5 hr_eq_remote var4 hr_eq_post"
        local IV_ENDO  "var3 var5 hr_eq_remote"
        local IV_INSTR "var6 var7 hr_eq_inst"
        local IV_EXOG  "var4 hr_eq_post"
    }
    else if "`s'" == "growth_endog_equity" {
        local OLS_RHS  "var3 var5 hr_growth_remote hr_eq_remote var4 hr_growth_post hr_eq_post"
        local IV_ENDO  "var3 var5 hr_growth_remote hr_eq_remote"
        local IV_INSTR "var6 var7 hr_growth_inst hr_eq_inst"
        local IV_EXOG  "var4 hr_growth_post hr_eq_post"
    }
    else if "`s'" == "hhi" {
        local OLS_RHS  "var3 var5 hr_hhi_remote var4 var11"
        local IV_ENDO  "var3 var5 hr_hhi_remote"
        local IV_INSTR "var6 var7 hr_hhi_inst"
        local IV_EXOG  "var4 var11"
    }
    else if "`s'" == "seniority" {
        local OLS_RHS  "var3 var5 hr_sen_remote var4 var14"
        local IV_ENDO  "var3 var5 hr_sen_remote"
        local IV_INSTR "var6 var7 hr_sen_inst"
        local IV_EXOG  "var4 var14"
    }
    else if "`s'" == "hhi_seniority" {
        local OLS_RHS  "var3 var5 hr_hhi_remote hr_sen_remote var4 var11 var14"
        local IV_ENDO  "var3 var5 hr_hhi_remote hr_sen_remote"
        local IV_INSTR "var6 var7 hr_hhi_inst hr_sen_inst"
        local IV_EXOG  "var4 var11 var14"
    }

    reghdfe total_contributions_q100 `OLS_RHS', `FE'
    local N = e(N)
    foreach p in `report_params' {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`s'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    ivreghdfe total_contributions_q100 (`IV_ENDO' = `IV_INSTR') `IV_EXOG', `FE'
    local rkf = e(rkf)
    local N   = e(N)
    foreach p in `report_params' {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`s'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
log close
