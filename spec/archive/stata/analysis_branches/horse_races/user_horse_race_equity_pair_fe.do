*====================================================================*
* user_horse_race_equity_pair_fe.do
*
* Pair-FE horse-race extension with explicit growth and equity toggles:
*   - baseline
*   - growth_endog
*   - equity
*   - growth_endog_equity
*
* Reports the core triple-diff terms plus the coefficients on the
* added horse-race controls so the table can show what each control is
* doing in the pair-FE specification.
*
* Output:
*   results/raw/user_horse_race_equity_pair_fe_<variant>/consolidated_results.csv
*====================================================================*

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
    di as error "Missing enriched LLM panel CSV: `enriched_panel_csv'"
    exit 601
}

local specname "user_horse_race_equity_pair_fe_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile llm_by_firm panel_plain g_postavg panel_growth

* 1) Load user panel and set pair FE
use "$processed_data/user_panel_`panel_variant'.dta", clear
local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"

* 2) Build strict any-equity firm signal with postings-based coverage
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

gen double var19 = covid * eq_any_firm
gen double var20 = covid * eq_any_firm * startup

save `panel_plain', replace

* 3) Build endogenous growth indicator (same construction as user_mechanisms_with_growth.do)
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    gen yh = hofd(date)
    format yh %th
    drop if date == 22797
    collapse (last) total_employees date (sum) join leave, by(companyname yh)
    gen byte covid = (yh >= 120)
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n > 1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    xtile tile_post_c = growth_rate_we_post_c, nq(2)
    save `g_postavg', replace
restore

use `panel_plain', clear
merge m:1 companyname using `g_postavg', keep(match) nogen
gen double var17_e = covid * tile_post_c
gen double var18_e = covid * tile_post_c * startup
save `panel_growth', replace

* 4) Output container
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  spec ///
    str40  param ///
    double coef se pval pre_mean ///
    double rkf nobs sample_n ///
    using `out', replace

local specs "baseline growth_endog equity growth_endog_equity"
local y total_contributions_q100

foreach s of local specs {
    if inlist("`s'", "growth_endog", "growth_endog_equity") {
        use `panel_growth', clear
    }
    else {
        use `panel_plain', clear
    }
    if inlist("`s'", "equity", "growth_endog_equity") {
        keep if eq_main_sample == 1
    }

    quietly count
    local sample_n = r(N)
    if `sample_n' == 0 continue

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    local EXOG "var4"
    if "`s'" == "growth_endog" {
        local EXOG "var4 var17_e var18_e"
    }
    else if "`s'" == "equity" {
        local EXOG "var4 var19 var20"
    }
    else if "`s'" == "growth_endog_equity" {
        local EXOG "var4 var17_e var18_e var19 var20"
    }

    capture noisily reghdfe `y' var3 var5 `EXOG', `FE'
    if !_rc {
        local nobs = e(N)
        local report_params "var3 var5 var17_e var18_e var19 var20"
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
            post handle ("OLS") ("`s'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`nobs') (`sample_n')
        }
    }

    capture noisily ivreghdfe `y' (var3 var5 = var6 var7) `EXOG', `FE'
    if !_rc {
        local rkf = .
        capture local rkf = e(rkf)
        local nobs = e(N)
        local report_params "var3 var5 var17_e var18_e var19 var20"
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
            post handle ("IV") ("`s'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`nobs') (`sample_n')
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
log close
