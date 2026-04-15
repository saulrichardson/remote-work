*============================================================*
* firm_scaling_llm_equity_mechanism_sweep.do
*
* Goal: Test whether alternative "equity as mechanism/control" definitions
* attenuate the baseline Remote×Post×Startup coefficient in the firm scaling
* growth regression.
*
* Backfill-only convention:
*   - If a firm×half-year cell is not present in the LLM equity panel,
*     equity measures are coded as 0 (no missingness controls).
*
* Output:
*   results/raw/firm_scaling_llm_equity_mechanism_sweep/consolidated_results.csv
*============================================================*

args llm_panel_csv

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

local specname "firm_scaling_llm_equity_mechanism_sweep"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

*------------------------------------------------------------*
* 1) Load firm panel and merge LLM equity signals by firm_id_key×yh
*------------------------------------------------------------*
tempfile base_panel llm_panel panel_ready

use "$processed_data/firm_panel.dta", clear
gen str244 __firm_name_key = lower(trim(companyname))
gen str10 __yh_key = string(dofh(yh), "%tdCCYY-NN-DD")
save `base_panel', replace

preserve
import delimited using "`llm_panel_csv'", clear varnames(1)
keep firm_id_key yh llm_equity_any llm_equity_share_parse_ok llm_n_equity_true
rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in llm_equity_any llm_equity_share_parse_ok llm_n_equity_true {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_panel', replace
restore

use `base_panel', clear
merge 1:1 __firm_name_key __yh_key using `llm_panel', nogen keep(master match)

* Backfill convention: missing/unobserved equity fields are 0
gen double eq_any_fh   = llm_equity_any
gen double eq_share_fh = llm_equity_share_parse_ok
gen double eq_count_fh = llm_n_equity_true

foreach v in eq_any_fh eq_share_fh eq_count_fh {
    replace `v' = 0 if missing(`v')
}
replace eq_any_fh = 0 if eq_any_fh < 0 | eq_any_fh > 1
replace eq_share_fh = 0 if eq_share_fh < 0 | eq_share_fh > 1
replace eq_count_fh = 0 if eq_count_fh < 0

gen double eq_count_log_fh = ln(1 + eq_count_fh)

* Firm-level summaries (firm panel is already firm×yh)
bysort firm_id: egen double eq_any_firm = max(eq_any_fh)
replace eq_any_firm = 0 if missing(eq_any_firm)

bysort firm_id: egen double eq_share_firm = mean(eq_share_fh)
replace eq_share_firm = 0 if missing(eq_share_firm)

bysort firm_id: egen double eq_share_firm_post = mean(eq_share_fh) if covid == 1
replace eq_share_firm_post = 0 if missing(eq_share_firm_post)

bysort firm_id: egen double eq_countlog_firm = mean(eq_count_log_fh)
replace eq_countlog_firm = 0 if missing(eq_countlog_firm)

* High-equity indicator: top quartile of post-period mean share
tempvar __tag_firm __share_q
egen byte `__tag_firm' = tag(firm_id)
xtile `__share_q' = eq_share_firm_post if `__tag_firm' == 1, nq(4)
gen byte eq_share_firm_post_topq = (`__share_q' == 4) if `__tag_firm' == 1
replace eq_share_firm_post_topq = 0 if missing(eq_share_firm_post_topq)
bysort firm_id: egen byte eq_share_firm_post_topq_firm = max(eq_share_firm_post_topq)
drop eq_share_firm_post_topq
rename eq_share_firm_post_topq_firm eq_share_firm_post_topq
drop `__share_q'

*------------------------------------------------------------*
* 2) Define equity control variants (post-shift controls)
*------------------------------------------------------------*
gen double z_cell_any          = covid * eq_any_fh
gen double z_cell_any_startup  = covid * eq_any_fh * startup
gen double z_cell_share        = covid * eq_share_fh
gen double z_cell_share_startup= covid * eq_share_fh * startup
gen double z_cell_countlog     = covid * eq_count_log_fh
gen double z_cell_countlog_startup = covid * eq_count_log_fh * startup

gen double z_firm_any          = covid * eq_any_firm
gen double z_firm_any_startup  = covid * eq_any_firm * startup
gen double z_firm_share_post   = covid * eq_share_firm_post
gen double z_firm_share_post_startup = covid * eq_share_firm_post * startup
gen double z_firm_share_topq   = covid * eq_share_firm_post_topq
gen double z_firm_share_topq_startup = covid * eq_share_firm_post_topq * startup
gen double z_firm_countlog     = covid * eq_countlog_firm
gen double z_firm_countlog_startup = covid * eq_countlog_firm * startup

save `panel_ready', replace

*------------------------------------------------------------*
* 3) Regression loop (baseline firm scaling spec; growth outcome)
*------------------------------------------------------------*
local outcome "growth_rate_we"
summarize `outcome' if covid == 0, meanonly
local pre_mean = r(mean)

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str32 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local spec_variants ///
    baseline ///
    eq_firm_any ///
    eq_firm_share_post ///
    eq_firm_share_topq_post ///
    eq_firm_countlog ///
    eq_cell_any ///
    eq_cell_share ///
    eq_cell_countlog

foreach spec_variant of local spec_variants {
    use `panel_ready', clear

    local ols_rhs "var3 var5 var4"
    local iv_endo "var3 var5"
    local iv_inst "var6 var7"
    local iv_exog "var4"

    if "`spec_variant'" == "eq_firm_any" {
        local ols_rhs "`ols_rhs' z_firm_any z_firm_any_startup"
        local iv_exog "`iv_exog' z_firm_any z_firm_any_startup"
    }
    else if "`spec_variant'" == "eq_firm_share_post" {
        local ols_rhs "`ols_rhs' z_firm_share_post z_firm_share_post_startup"
        local iv_exog "`iv_exog' z_firm_share_post z_firm_share_post_startup"
    }
    else if "`spec_variant'" == "eq_firm_share_topq_post" {
        local ols_rhs "`ols_rhs' z_firm_share_topq z_firm_share_topq_startup"
        local iv_exog "`iv_exog' z_firm_share_topq z_firm_share_topq_startup"
    }
    else if "`spec_variant'" == "eq_firm_countlog" {
        local ols_rhs "`ols_rhs' z_firm_countlog z_firm_countlog_startup"
        local iv_exog "`iv_exog' z_firm_countlog z_firm_countlog_startup"
    }
    else if "`spec_variant'" == "eq_cell_any" {
        local ols_rhs "`ols_rhs' z_cell_any z_cell_any_startup"
        local iv_exog "`iv_exog' z_cell_any z_cell_any_startup"
    }
    else if "`spec_variant'" == "eq_cell_share" {
        local ols_rhs "`ols_rhs' z_cell_share z_cell_share_startup"
        local iv_exog "`iv_exog' z_cell_share z_cell_share_startup"
    }
    else if "`spec_variant'" == "eq_cell_countlog" {
        local ols_rhs "`ols_rhs' z_cell_countlog z_cell_countlog_startup"
        local iv_exog "`iv_exog' z_cell_countlog z_cell_countlog_startup"
    }

    * OLS
    capture quietly reghdfe `outcome' `ols_rhs', absorb(firm_id yh) vce(cluster firm_id)
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
    capture quietly ivreghdfe `outcome' (`iv_endo' = `iv_inst') `iv_exog', absorb(firm_id yh) vce(cluster firm_id)
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
