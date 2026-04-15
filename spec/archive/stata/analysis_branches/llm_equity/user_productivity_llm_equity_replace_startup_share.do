*============================================================*
* user_productivity_llm_equity_replace_startup_share.do
*
* Goal:
*   "Replace-startup" variant using a *share* equity measure.
*   This mirrors the reduced DD table used in the equity tech note, but
*   replaces the firm-level LLM equity indicator with a firm-level measure:
*     - Post-period mean share of postings (with descriptions) classified
*       by the LLM as offering equity compensation.
*
* Equity share construction:
*   1) At firm×half-year, define within-cell share:
*        eq_shp_fh = llm_n_equity_true_raw / n_postings_desc_total
*      where n_postings_desc_total counts postings with descriptions.
*   2) At the firm level, define post-period mean:
*        eq_shp_post_mean_f = mean(eq_shp_fh) over post half-years (covid==1)
*      (0 when no post-period postings are observed).
*
* Specification:
*   y_ifh = β3 (Remote×Post) + βS (Remote×Post×Share_f) + θ (Post×Share_f)
*           + α_i + α_f + τ_h + ε_ifh
*
* Output:
*   results/raw/user_productivity_llm_equity_replace_startup_share_<panel>/consolidated_results.csv
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

* Stata argument parsing can drop truly-empty args; allow `default` / `.`.
if "`enriched_panel_csv'" == "" | inlist(lower("`enriched_panel_csv'"), ".", "default") {
    local enriched_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity_enriched.csv"
}
capture confirm file "`enriched_panel_csv'"
if _rc {
    di as error "Missing enriched LLM equity panel: `enriched_panel_csv'"
    exit 601
}

local specname "user_productivity_llm_equity_replace_startup_share_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

*------------------------------------------------------------*
* 1) Load enriched firm×half-year panel (needed columns only)
*------------------------------------------------------------*
tempfile llm_by_firm
preserve
import delimited using "`enriched_panel_csv'", clear varnames(1)

keep firm_id_key yh llm_n_equity_true_raw n_postings_desc_total

rename firm_id_key __firm_name_key
rename yh __yh_key

replace __firm_name_key = lower(trim(__firm_name_key))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")

foreach v in llm_n_equity_true_raw n_postings_desc_total {
    capture destring `v', replace force
    replace `v' = 0 if missing(`v')
    replace `v' = 0 if `v' < 0
}

drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_firm', replace
restore

*------------------------------------------------------------*
* 2) Load user panel and merge enriched equity panel
*------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear

gen str244 __firm_name_key = lower(trim(companyname))
replace __firm_name_key = "" if inlist(__firm_name_key, ".", "", "nan", "none")
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")

merge m:1 __firm_name_key __yh_key using `llm_by_firm', keep(master match) nogen

replace llm_n_equity_true_raw = 0 if missing(llm_n_equity_true_raw)
replace n_postings_desc_total = 0 if missing(n_postings_desc_total)

* Within-cell share among postings with descriptions (treat denom==0 as 0).
gen double eq_shp_fh = cond(n_postings_desc_total > 0, llm_n_equity_true_raw / n_postings_desc_total, 0)
replace eq_shp_fh = 0 if missing(eq_shp_fh) | eq_shp_fh < 0
replace eq_shp_fh = 1 if eq_shp_fh > 1

* Firm-level post-period mean share (computed on one row per firm×yh).
tempvar __tag_fy
egen byte `__tag_fy' = tag(firm_id yh)
gen double __eq_shp_post = eq_shp_fh if `__tag_fy' == 1 & covid == 1
bysort firm_id: egen double eq_shp_post_mean_f = mean(__eq_shp_post)
replace eq_shp_post_mean_f = 0 if missing(eq_shp_post_mean_f)
drop __eq_shp_post

* Post-shift term and Remote×Post×Share interaction.
gen double eq_shp_post_mean_f_covid = eq_shp_post_mean_f * covid
gen double var3_eq_shp_post = var3 * eq_shp_post_mean_f
gen double var6_eq_shp_post = var6 * eq_shp_post_mean_f

*------------------------------------------------------------*
* 3) Regression (OLS + IV) + export
*------------------------------------------------------------*
local outcome "total_contributions_q100"
summarize `outcome' if covid == 0, meanonly
local pre_mean = r(mean)

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str12 sample_mode ///
    str32 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    double n_firms n_users ///
    using `out', replace

* Sample counts for reporting
tempvar __tag_firm __tag_user
egen byte `__tag_firm' = tag(firm_id)
egen byte `__tag_user' = tag(user_id)
quietly count if `__tag_firm' == 1
local n_firms = r(N)
quietly count if `__tag_user' == 1
local n_users = r(N)

local params "var3 var3_eq_shp_post eq_shp_post_mean_f_covid"

* OLS
capture noisily reghdfe `outcome' var3 var3_eq_shp_post eq_shp_post_mean_f_covid, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
if _rc {
    di as error "OLS regression failed."
    exit 459
}
local nobs = e(N)
foreach p of local params {
    local b  = _b[`p']
    local se = _se[`p']
    local pval = .
    if (`se' == 0 | missing(`se')) {
        local b = .
        local se = .
    }
    else if `se' < . & e(df_r) < . {
        local t = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
    }
    post handle ("OLS") ("all") ("share_post_mean") ("`outcome'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') (.) (`nobs') (`n_firms') (`n_users')
}

* IV (instrument var3 and var3×share with teleworkable counterparts)
capture noisily ivreghdfe `outcome' ///
    (var3 var3_eq_shp_post = var6 var6_eq_shp_post) ///
    eq_shp_post_mean_f_covid, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
if _rc {
    di as error "IV regression failed."
    exit 471
}
local nobs = e(N)
local rkf = .
capture local rkf = e(rkf)
foreach p of local params {
    local b  = _b[`p']
    local se = _se[`p']
    local pval = .
    if (`se' == 0 | missing(`se')) {
        local b = .
        local se = .
    }
    else if `se' < . & e(df_r) < . {
        local t = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
    }
    post handle ("IV") ("all") ("share_post_mean") ("`outcome'") ("`p'") ///
        (`b') (`se') (`pval') (`pre_mean') (`rkf') (`nobs') (`n_firms') (`n_users')
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
di as result "→ CSV : `result_dir'/consolidated_results.csv"

log close

