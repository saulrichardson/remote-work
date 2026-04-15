*============================================================*
* user_productivity_llm_equity_mechanism_sweep_pair_fe_software.do
*
* Goal: Same as the pair-FE equity mechanism sweep, but using SOFTWARE-only
* strict LLM equity measures from the enriched equity panel.
*
* Backfill-only convention:
*   - Missing/unobserved equity fields are coded as 0 (no missingness controls).
*
* Output:
*   results/raw/user_productivity_llm_equity_mechanism_sweep_pair_fe_software_<panel_variant>/consolidated_results.csv
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
    di as error "Missing enriched LLM equity panel: `enriched_panel_csv'"
    exit 601
}

local specname "user_productivity_llm_equity_mechanism_sweep_pair_fe_software_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

*------------------------------------------------------------*
* 1) Build firm_id×yh LLM merge (from firm panel keys)
*------------------------------------------------------------*
tempfile firm_keys llm_by_name llm_by_firm

use "$processed_data/firm_panel.dta", clear
keep firm_id companyname yh
duplicates drop firm_id yh, force
gen str244 __firm_name_key = lower(trim(companyname))
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
save `firm_keys', replace

preserve
import delimited using "`enriched_panel_csv'", clear varnames(1)
* Stata varname limit (32 chars) can force long headers to import as v##.
* In that case, the full header is stored in the variable label. We map by label.
local __share_label "llm_equity_share_parse_ok_software_strict"
local __count_label "llm_equity_count_parse_ok_software_strict"

local __share_var ""
local __count_var ""
foreach __v of varlist _all {
    local __lab : variable label `__v'
    if "`__lab'" == "`__share_label'" local __share_var "`__v'"
    if "`__lab'" == "`__count_label'" local __count_var "`__v'"
}
if "`__share_var'" == "" {
    di as error "Unable to locate software-strict share column (`__share_label') after import."
    exit 198
}
if "`__count_var'" == "" {
    di as error "Unable to locate software-strict count column (`__count_label') after import."
    exit 198
}

rename `__share_var' llm_eq_share_sw_strict
rename `__count_var' llm_eq_count_sw_strict

keep firm_id_key yh ///
    llm_equity_any_software_strict ///
    llm_eq_share_sw_strict ///
    llm_eq_count_sw_strict
rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in ///
    llm_equity_any_software_strict ///
    llm_eq_share_sw_strict ///
    llm_eq_count_sw_strict {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_name', replace
restore

use `firm_keys', clear
merge 1:1 __firm_name_key __yh_key using `llm_by_name', keep(master match) nogen
keep firm_id yh ///
    llm_equity_any_software_strict ///
    llm_eq_share_sw_strict ///
    llm_eq_count_sw_strict
duplicates drop firm_id yh, force
save `llm_by_firm', replace

*------------------------------------------------------------*
* 2) Load user panel and attach equity measures (backfill=0)
*------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `llm_by_firm', keep(master match) nogen

gen double eq_any_soft_fh   = llm_equity_any_software_strict
gen double eq_share_soft_fh = llm_eq_share_sw_strict
gen double eq_count_soft_fh = llm_eq_count_sw_strict

foreach v in eq_any_soft_fh eq_share_soft_fh eq_count_soft_fh {
    replace `v' = 0 if missing(`v')
}
replace eq_any_soft_fh = 0 if eq_any_soft_fh < 0 | eq_any_soft_fh > 1
replace eq_share_soft_fh = 0 if eq_share_soft_fh < 0 | eq_share_soft_fh > 1
replace eq_count_soft_fh = 0 if eq_count_soft_fh < 0

gen double eq_count_soft_log_fh = ln(1 + eq_count_soft_fh)

* Firm-level summaries computed on unique firm×yh cells to avoid user-weighting
tempvar __tag_fy
egen byte `__tag_fy' = tag(firm_id yh)

bysort firm_id: egen double eq_any_soft_firm = max(eq_any_soft_fh)
replace eq_any_soft_firm = 0 if missing(eq_any_soft_firm)

gen double __eq_share_soft_post = eq_share_soft_fh if `__tag_fy' == 1 & covid == 1
bysort firm_id: egen double eq_share_soft_firm_post = mean(__eq_share_soft_post)
drop __eq_share_soft_post
replace eq_share_soft_firm_post = 0 if missing(eq_share_soft_firm_post)

*------------------------------------------------------------*
* 3) Define equity control variants (software strict; post-shift controls)
*------------------------------------------------------------*
gen double z_soft_cell_any          = covid * eq_any_soft_fh
gen double z_soft_cell_any_startup  = covid * eq_any_soft_fh * startup
gen double z_soft_cell_share        = covid * eq_share_soft_fh
gen double z_soft_cell_share_startup= covid * eq_share_soft_fh * startup
gen double z_soft_cell_countlog     = covid * eq_count_soft_log_fh
gen double z_soft_cell_countlog_startup = covid * eq_count_soft_log_fh * startup

gen double z_soft_firm_any          = covid * eq_any_soft_firm
gen double z_soft_firm_any_startup  = covid * eq_any_soft_firm * startup
gen double z_soft_firm_share_post   = covid * eq_share_soft_firm_post
gen double z_soft_firm_share_post_startup = covid * eq_share_soft_firm_post * startup

*------------------------------------------------------------*
* 4) Regression loop (pair FE)
*------------------------------------------------------------*
local outcome "total_contributions_q100"
summarize `outcome' if covid == 0, meanonly
local pre_mean = r(mean)

local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str40 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local spec_variants ///
    baseline ///
    soft_firm_any ///
    soft_firm_share_post ///
    soft_cell_any ///
    soft_cell_share ///
    soft_cell_countlog

foreach spec_variant of local spec_variants {
    local ols_rhs "var3 var5 var4"
    local iv_endo "var3 var5"
    local iv_inst "var6 var7"
    local iv_exog "var4"

    if "`spec_variant'" == "soft_firm_any" {
        local ols_rhs "`ols_rhs' z_soft_firm_any z_soft_firm_any_startup"
        local iv_exog "`iv_exog' z_soft_firm_any z_soft_firm_any_startup"
    }
    else if "`spec_variant'" == "soft_firm_share_post" {
        local ols_rhs "`ols_rhs' z_soft_firm_share_post z_soft_firm_share_post_startup"
        local iv_exog "`iv_exog' z_soft_firm_share_post z_soft_firm_share_post_startup"
    }
    else if "`spec_variant'" == "soft_cell_any" {
        local ols_rhs "`ols_rhs' z_soft_cell_any z_soft_cell_any_startup"
        local iv_exog "`iv_exog' z_soft_cell_any z_soft_cell_any_startup"
    }
    else if "`spec_variant'" == "soft_cell_share" {
        local ols_rhs "`ols_rhs' z_soft_cell_share z_soft_cell_share_startup"
        local iv_exog "`iv_exog' z_soft_cell_share z_soft_cell_share_startup"
    }
    else if "`spec_variant'" == "soft_cell_countlog" {
        local ols_rhs "`ols_rhs' z_soft_cell_countlog z_soft_cell_countlog_startup"
        local iv_exog "`iv_exog' z_soft_cell_countlog z_soft_cell_countlog_startup"
    }

    * OLS
    capture quietly reghdfe `outcome' `ols_rhs', `FE'
    if _rc continue
    local nobs = e(N)
    foreach p in var3 var5 {
        local b  = _b[`p']
        local se = _se[`p']
        local pval = .
        if `se' < . & `se' != 0 & e(df_r) < . {
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
        }
        post handle ("OLS") ("`spec_variant'") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (.) (`nobs')
    }

    * IV
    capture quietly ivreghdfe `outcome' (`iv_endo' = `iv_inst') `iv_exog', `FE'
    if _rc continue
    local nobs = e(N)
    local rkf = .
    capture local rkf = e(rkf)
    foreach p in var3 var5 {
        local b  = _b[`p']
        local se = _se[`p']
        local pval = .
        if `se' < . & `se' != 0 & e(df_r) < . {
            local t = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
        }
        post handle ("IV") ("`spec_variant'") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (`rkf') (`nobs')
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
di as result "→ CSV : `result_dir'/consolidated_results.csv"
capture log close
