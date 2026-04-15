*====================================================================*
* user_horse_race_startup_swapped.do
*
* Baseline-FE horse-race extension that keeps the baseline startup
* triple-diff terms and adds startup-swapped controls on the remote
* margin:
*   - baseline
*   - labor_scaling
*   - equity_comp
*   - labor_scaling_equity_comp
*
* For each added control Z, the new channel is:
*   Z_post    = Post x Z
*   Z_remote  = Remote x Post x Z
*   Z_inst    = Teleworkable x Post x Z
*
* This version harmonizes the growth channel with the pair-FE and
* mechanisms specs by constructing the post-COVID firm-growth split
* directly from Scoop_Positions_Firm_Collapse2.csv. All columns are
* estimated on the same merged sample.
*
* Output:
*   results/raw/user_horse_race_startup_swapped_<variant>/consolidated_results.csv
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

local specname "user_horse_race_startup_swapped_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile equity_by_firm g_postavg panel_common

* 1) Build firm x yh equity signal (strict any-equity, backfilled).
import delimited using "`enriched_panel_csv'", clear varnames(1)
keep firm_id_key yh llm_n_parse_ok_raw llm_equity_any_strict
rename firm_id_key __firm_name_key
rename yh __yh_key
replace __firm_name_key = lower(trim(__firm_name_key))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
foreach v in llm_n_parse_ok_raw llm_equity_any_strict {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `equity_by_firm', replace

* 2) Build post-COVID firm-growth indicator (harmonized with pair FE and mechanisms specs).
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

* 3) Load user panel and merge controls. Keep the same merged sample for every column.
use "$processed_data/user_panel_`panel_variant'.dta", clear

gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")

merge m:1 __firm_name_key __yh_key using `equity_by_firm', keep(master match) nogen
merge m:1 companyname using `g_postavg', keep(match) nogen

foreach v in llm_n_parse_ok_raw llm_equity_any_strict tile_post_c {
    capture destring `v', replace force
}

gen byte eq_has_parse = llm_n_parse_ok_raw > 0 if !missing(llm_n_parse_ok_raw)
replace eq_has_parse = 0 if missing(eq_has_parse)

gen double eq_any_obs = cond(eq_has_parse == 1, llm_equity_any_strict, 0)
replace eq_any_obs = 0 if missing(eq_any_obs)
replace eq_any_obs = . if eq_any_obs < 0 | eq_any_obs > 1

bysort firm_id: egen double eq_any_firm = max(eq_any_obs)
replace eq_any_firm = 0 if missing(eq_any_firm)

gen double hr_eq_post   = covid * eq_any_firm
gen double hr_eq_remote = var3 * eq_any_firm
gen double hr_eq_inst   = var6 * eq_any_firm

gen double hr_scale_post   = covid * tile_post_c
gen double hr_scale_remote = var3 * tile_post_c
gen double hr_scale_inst   = var6 * tile_post_c

save `panel_common', replace

* 4) Output container.
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

local FE "absorb(user_id firm_id yh) vce(cluster user_id)"
local specs "baseline labor_scaling equity_comp labor_scaling_equity_comp"
local y total_contributions_q100

foreach s of local specs {
    use `panel_common', clear

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
    local report_params "var3 var5 hr_scale_post hr_scale_remote hr_eq_post hr_eq_remote"

    if "`s'" == "labor_scaling" {
        local ols_rhs "var3 var5 hr_scale_remote var4 hr_scale_post"
        local iv_endo "var3 var5 hr_scale_remote"
        local iv_inst "var6 var7 hr_scale_inst"
        local iv_exog "var4 hr_scale_post"
    }
    else if "`s'" == "equity_comp" {
        local ols_rhs "var3 var5 hr_eq_remote var4 hr_eq_post"
        local iv_endo "var3 var5 hr_eq_remote"
        local iv_inst "var6 var7 hr_eq_inst"
        local iv_exog "var4 hr_eq_post"
    }
    else if "`s'" == "labor_scaling_equity_comp" {
        local ols_rhs "var3 var5 hr_scale_remote hr_eq_remote var4 hr_scale_post hr_eq_post"
        local iv_endo "var3 var5 hr_scale_remote hr_eq_remote"
        local iv_inst "var6 var7 hr_scale_inst hr_eq_inst"
        local iv_exog "var4 hr_scale_post hr_eq_post"
    }

    capture noisily reghdfe `y' `ols_rhs', `FE'
    if _rc {
        di as error "OLS regression failed for spec `s'"
        exit 459
    }
    local nobs = e(N)
    foreach p of local report_params {
        capture local b = _b[`p']
        if _rc continue
        capture local se = _se[`p']
        if _rc continue
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
        capture local b = _b[`p']
        if _rc continue
        capture local se = _se[`p']
        if _rc continue
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
