*====================================================================*
* user_horse_race_keep_remote.do
*
* Canonical horse-race design where competing channels stay on the
* remote margin:
*   - baseline
*   - firm_growth
*   - equity_comp
*   - firm_growth_equity_comp
*
* FE structure is selected by argument:
*   - baseline : firm, worker, and half-year fixed effects
*   - pair     : firm x worker and half-year fixed effects
*
* Sample rule:
*   - baseline column keeps the original panel support
*   - firm-growth columns require non-missing post-COVID growth bin
*   - equity columns use postings-covered equity support only
*====================================================================*

args panel_variant fe_mode enriched_panel_csv
if "`panel_variant'" == "" local panel_variant "precovid"
if "`fe_mode'" == "" local fe_mode "pair"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

if !inlist("`fe_mode'", "baseline", "pair") {
    di as error "fe_mode must be baseline or pair"
    exit 198
}

if "`enriched_panel_csv'" == "" local enriched_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv"
capture confirm file "`enriched_panel_csv'"
if _rc {
    di as error "Missing enriched LLM panel CSV: `enriched_panel_csv'"
    exit 601
}

local specname "user_horse_race_keep_remote_`fe_mode'_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile equity_by_firm growth_bins panel_all

* 1) Build firm x half-year equity audit panel.
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
save `equity_by_firm', replace

* 2) Build post-COVID firm-growth indicator from the raw positions panel.
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
save `growth_bins', replace

* 3) Load user panel and merge supports.
use "$processed_data/user_panel_`panel_variant'.dta", clear

gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")

merge m:1 __firm_name_key __yh_key using `equity_by_firm', keep(master match) nogen
merge m:1 companyname using `growth_bins', keep(master match) nogen

foreach v in n_postings_desc_total n_keyword_hit_candidates llm_n_parse_ok_raw llm_equity_any_strict tile_post_c {
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
gen byte has_growth = !missing(tile_post_c)

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

gen double hr_growth_post = covid * tile_post_c
gen double hr_growth_remote = var3 * tile_post_c
gen double hr_growth_inst = var6 * tile_post_c

gen double hr_eq_post = covid * eq_any_firm
gen double hr_eq_remote = var3 * eq_any_firm
gen double hr_eq_inst = var6 * eq_any_firm

save `panel_all', replace

* 4) FE mode.
if "`fe_mode'" == "baseline" {
    local FE "absorb(user_id firm_id yh) vce(cluster user_id)"
}
else if "`fe_mode'" == "pair" {
    local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"
}

* 5) Output container.
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

local specs "baseline firm_growth equity_comp firm_growth_equity_comp"
local y total_contributions_q100

foreach s of local specs {
    use `panel_all', clear

    if inlist("`s'", "firm_growth", "firm_growth_equity_comp") {
        keep if has_growth == 1
    }
    if inlist("`s'", "equity_comp", "firm_growth_equity_comp") {
        keep if eq_main_sample == 1
    }

    quietly count
    local sample_n = r(N)
    if `sample_n' == 0 {
        di as error "Empty sample for spec `s'"
        exit 459
    }

    quietly summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    local ols_rhs "var3 var5 var4"
    local iv_endo "var3 var5"
    local iv_inst "var6 var7"
    local iv_exog "var4"

    if "`s'" == "firm_growth" {
        local ols_rhs "var3 var5 hr_growth_remote var4 hr_growth_post"
        local iv_endo "var3 var5 hr_growth_remote"
        local iv_inst "var6 var7 hr_growth_inst"
        local iv_exog "var4 hr_growth_post"
    }
    else if "`s'" == "equity_comp" {
        local ols_rhs "var3 var5 hr_eq_remote var4 hr_eq_post"
        local iv_endo "var3 var5 hr_eq_remote"
        local iv_inst "var6 var7 hr_eq_inst"
        local iv_exog "var4 hr_eq_post"
    }
    else if "`s'" == "firm_growth_equity_comp" {
        local ols_rhs "var3 var5 hr_growth_remote hr_eq_remote var4 hr_growth_post hr_eq_post"
        local iv_endo "var3 var5 hr_growth_remote hr_eq_remote"
        local iv_inst "var6 var7 hr_growth_inst hr_eq_inst"
        local iv_exog "var4 hr_growth_post hr_eq_post"
    }

    capture noisily reghdfe `y' `ols_rhs', `FE'
    if _rc {
        di as error "OLS regression failed for spec `s'"
        exit 459
    }
    local nobs = e(N)
    local report_params "var3 var5"
    foreach p of local report_params {
        local b = _b[`p']
        local se = _se[`p']
        local pval = .
        if `se' < . & `se' != 0 & e(df_r) < . {
            local t = `b' / `se'
            local pval = 2 * ttail(e(df_r), abs(`t'))
        }
        post handle ("OLS") ("`s'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`nobs') (`sample_n')
    }

    capture noisily ivreghdfe `y' (`iv_endo' = `iv_inst') `iv_exog', `FE'
    if _rc {
        di as error "IV regression failed for spec `s'"
        exit 471
    }
    local rkf = .
    capture local rkf = e(rkf)
    local nobs = e(N)
    foreach p of local report_params {
        local b = _b[`p']
        local se = _se[`p']
        local pval = .
        if `se' < . & `se' != 0 & e(df_r) < . {
            local t = `b' / `se'
            local pval = 2 * ttail(e(df_r), abs(`t'))
        }
        post handle ("IV") ("`s'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`nobs') (`sample_n')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "-> CSV written to `result_dir'/consolidated_results.csv"
log close
