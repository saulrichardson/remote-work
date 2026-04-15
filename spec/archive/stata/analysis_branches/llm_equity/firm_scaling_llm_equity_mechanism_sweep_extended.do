*============================================================*
* firm_scaling_llm_equity_mechanism_sweep_extended.do
*
* Goal: Iterate on alternative equity definitions (including specific equity
* types mentioned in postings) to see whether any control attenuates the
* baseline Remote×Post×Startup coefficient (var5) in the firm scaling design.
*
* Backfill-only convention:
*   - If a firm×half-year cell is not present in the LLM equity panel,
*     equity measures are coded as 0 (no missingness controls).
*
* Output:
*   results/raw/firm_scaling_llm_equity_mechanism_sweep_extended/consolidated_results.csv
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

local specname "firm_scaling_llm_equity_mechanism_sweep_extended"
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
keep firm_id_key yh ///
    llm_n_parse_ok ///
    llm_n_equity_true ///
    llm_equity_any ///
    llm_equity_share_parse_ok ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_other_equity_mentioned
rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in ///
    llm_n_parse_ok ///
    llm_n_equity_true ///
    llm_equity_any ///
    llm_equity_share_parse_ok ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_other_equity_mentioned {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_panel', replace
restore

use `base_panel', clear
merge 1:1 __firm_name_key __yh_key using `llm_panel', nogen keep(master match)

* Backfill convention: missing/unobserved equity fields are 0
foreach v in ///
    llm_n_parse_ok ///
    llm_n_equity_true ///
    llm_equity_any ///
    llm_equity_share_parse_ok ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_other_equity_mentioned {
    replace `v' = 0 if missing(`v')
}

replace llm_equity_any = 0 if llm_equity_any < 0 | llm_equity_any > 1
replace llm_equity_share_parse_ok = 0 if llm_equity_share_parse_ok < 0 | llm_equity_share_parse_ok > 1
replace llm_n_parse_ok = 0 if llm_n_parse_ok < 0
replace llm_n_equity_true = 0 if llm_n_equity_true < 0

foreach v in ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_other_equity_mentioned {
    replace `v' = 0 if `v' < 0
}

* Cell-level equity measures (fh = firm×half-year; firm_panel is already firm×yh)
gen double eq_any_fh   = llm_equity_any
gen double eq_share_fh = llm_equity_share_parse_ok
gen double eq_count_fh = llm_n_equity_true
gen double eq_count_log_fh = ln(1 + eq_count_fh)

* Type-specific counts/shares/logs
gen double opt_cnt_fh   = llm_n_stock_options_mentioned
gen double rsu_cnt_fh   = llm_n_rsu_mentioned
gen double restr_cnt_fh = llm_n_restricted_stock_mentioned
gen double espp_cnt_fh  = llm_n_espp_mentioned
gen double other_cnt_fh = llm_n_other_equity_mentioned

foreach v in opt_cnt_fh rsu_cnt_fh restr_cnt_fh espp_cnt_fh other_cnt_fh {
    replace `v' = 0 if missing(`v')
    replace `v' = 0 if `v' < 0
}

gen double restr_share_fh = cond(llm_n_parse_ok > 0, restr_cnt_fh / llm_n_parse_ok, 0)
replace restr_share_fh = 0 if missing(restr_share_fh) | restr_share_fh < 0 | restr_share_fh > 1

gen double opt_log_fh   = ln(1 + opt_cnt_fh)
gen double rsu_log_fh   = ln(1 + rsu_cnt_fh)
gen double restr_log_fh = ln(1 + restr_cnt_fh)
gen double espp_log_fh  = ln(1 + espp_cnt_fh)
gen double other_log_fh = ln(1 + other_cnt_fh)

* Firm-level post-period means (as in growth mechanism specs)
bysort firm_id: egen double restr_share_post = mean(restr_share_fh) if covid == 1
replace restr_share_post = 0 if missing(restr_share_post)

foreach v in opt_log_fh rsu_log_fh restr_log_fh espp_log_fh other_log_fh eq_count_log_fh {
    bysort firm_id: egen double `v'_post = mean(`v') if covid == 1
    replace `v'_post = 0 if missing(`v'_post)
}

* Firm-level any equity in post period (max)
bysort firm_id: egen double eq_any_post = max(eq_any_fh) if covid == 1
replace eq_any_post = 0 if missing(eq_any_post)

*------------------------------------------------------------*
* 2) Define control variants (post-shift controls)
*------------------------------------------------------------*
gen double z_eq_any         = covid * eq_any_post
gen double z_eq_any_su      = covid * eq_any_post * startup

gen double z_restr_share    = covid * restr_share_post
gen double z_restr_share_su = covid * restr_share_post * startup

gen double z_restr_log      = covid * restr_log_fh_post
gen double z_restr_log_su   = covid * restr_log_fh_post * startup

gen double z_rsu_log        = covid * rsu_log_fh_post
gen double z_rsu_log_su     = covid * rsu_log_fh_post * startup

gen double z_opt_log        = covid * opt_log_fh_post
gen double z_opt_log_su     = covid * opt_log_fh_post * startup

gen double z_espp_log       = covid * espp_log_fh_post
gen double z_espp_log_su    = covid * espp_log_fh_post * startup

gen double z_other_log      = covid * other_log_fh_post
gen double z_other_log_su   = covid * other_log_fh_post * startup

gen double z_eq_cntlog      = covid * eq_count_log_fh_post
gen double z_eq_cntlog_su   = covid * eq_count_log_fh_post * startup

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
    str40 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local spec_variants ///
    baseline ///
    eq_any ///
    eq_cntlog ///
    restr_share ///
    restr_log ///
    rsu_log ///
    opt_log ///
    espp_log ///
    other_log

local ctl_baseline ""
local ctl_eq_any      "z_eq_any z_eq_any_su"
local ctl_eq_cntlog   "z_eq_cntlog z_eq_cntlog_su"
local ctl_restr_share "z_restr_share z_restr_share_su"
local ctl_restr_log   "z_restr_log z_restr_log_su"
local ctl_rsu_log     "z_rsu_log z_rsu_log_su"
local ctl_opt_log     "z_opt_log z_opt_log_su"
local ctl_espp_log    "z_espp_log z_espp_log_su"
local ctl_other_log   "z_other_log z_other_log_su"

foreach spec_variant of local spec_variants {
    use `panel_ready', clear

    local controls "`ctl_`spec_variant''"
    if "`spec_variant'" != "baseline" & "`controls'" == "" {
        di as error "No controls mapped for spec_variant=`spec_variant'."
        exit 198
    }

    local ols_rhs "var3 var5 var4 `controls'"
    local iv_endo "var3 var5"
    local iv_inst "var6 var7"
    local iv_exog "var4 `controls'"

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

