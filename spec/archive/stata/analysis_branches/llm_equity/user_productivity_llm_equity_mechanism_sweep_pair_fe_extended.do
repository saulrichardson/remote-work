*============================================================*
* user_productivity_llm_equity_mechanism_sweep_pair_fe_extended.do
*
* Goal: Iterate on "equity as mechanism/control" definitions to see if
* any alternative equity construction attenuates the baseline
* Remote×Post×Startup coefficient (var5) in the pair-FE user productivity
* design, similar to the growth mechanism columns.
*
* Backfill-only convention:
*   - If a firm×half-year cell is not present in the LLM equity panel,
*     equity measures are coded as 0 (no missingness controls).
*
* Output:
*   results/raw/user_productivity_llm_equity_mechanism_sweep_pair_fe_extended_<panel_variant>/consolidated_results.csv
*============================================================*

args panel_variant llm_panel_csv
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

if "`llm_panel_csv'" == "" local llm_panel_csv "$results/postings_description_equity/firm_merge/latest_firm_yh_llm_equity.csv"
capture confirm file "`llm_panel_csv'"
if _rc {
    di as error "Missing LLM panel CSV: `llm_panel_csv'"
    exit 601
}

local specname "user_productivity_llm_equity_mechanism_sweep_pair_fe_extended_`panel_variant'"
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
import delimited using "`llm_panel_csv'", clear varnames(1)
* Some very long headers can import as v## with the full header in the varlabel.
local __sar_label "llm_n_stock_appreciation_rights_mentioned"
local __sar_var ""
foreach __v of varlist _all {
    local __lab : variable label `__v'
    if "`__lab'" == "`__sar_label'" local __sar_var "`__v'"
}
if "`__sar_var'" != "" {
    rename `__sar_var' llm_n_stock_app_rights_ment
}
else {
    * If Stata truncates to a valid name (no varlabel), we expect this column not to be needed downstream.
    gen double llm_n_stock_app_rights_ment = 0
}

keep firm_id_key yh ///
    llm_n_parse_ok ///
    llm_n_equity_true ///
    llm_equity_any ///
    llm_equity_share_parse_ok ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_esop_mentioned ///
    llm_n_phantom_equity_mentioned ///
    llm_n_profit_interest_mentioned ///
    llm_n_carried_interest_mentioned ///
    llm_n_stock_app_rights_ment ///
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
    llm_n_esop_mentioned ///
    llm_n_phantom_equity_mentioned ///
    llm_n_profit_interest_mentioned ///
    llm_n_carried_interest_mentioned ///
    llm_n_stock_app_rights_ment ///
    llm_n_other_equity_mentioned {
    capture destring `v', replace force
}
drop if missing(__firm_name_key) | missing(__yh_key)
duplicates drop __firm_name_key __yh_key, force
save `llm_by_name', replace
restore

use `firm_keys', clear
merge 1:1 __firm_name_key __yh_key using `llm_by_name', keep(master match) nogen
keep firm_id yh ///
    llm_n_parse_ok ///
    llm_n_equity_true ///
    llm_equity_any ///
    llm_equity_share_parse_ok ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_esop_mentioned ///
    llm_n_phantom_equity_mentioned ///
    llm_n_profit_interest_mentioned ///
    llm_n_carried_interest_mentioned ///
    llm_n_stock_app_rights_ment ///
    llm_n_other_equity_mentioned
duplicates drop firm_id yh, force
save `llm_by_firm', replace

*------------------------------------------------------------*
* 2) Load user panel and attach equity measures (backfill=0)
*------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `llm_by_firm', keep(master match) nogen

* Backfill convention: missing/unobserved fields are 0
foreach v in ///
    llm_n_parse_ok ///
    llm_n_equity_true ///
    llm_equity_any ///
    llm_equity_share_parse_ok ///
    llm_n_stock_options_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_restricted_stock_mentioned ///
    llm_n_espp_mentioned ///
    llm_n_esop_mentioned ///
    llm_n_phantom_equity_mentioned ///
    llm_n_profit_interest_mentioned ///
    llm_n_carried_interest_mentioned ///
    llm_n_stock_app_rights_ment ///
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
    llm_n_esop_mentioned ///
    llm_n_phantom_equity_mentioned ///
    llm_n_profit_interest_mentioned ///
    llm_n_carried_interest_mentioned ///
    llm_n_stock_app_rights_ment ///
    llm_n_other_equity_mentioned {
    replace `v' = 0 if `v' < 0
}

* Cell-level baseline equity measures (fh = firm×half-year)
gen double eq_any_fh   = llm_equity_any
gen double eq_share_fh = llm_equity_share_parse_ok
gen double eq_count_fh = llm_n_equity_true
gen double eq_count_log_fh = ln(1 + eq_count_fh)

* Equity-type cell-level counts
gen double eq_opt_cnt_fh    = llm_n_stock_options_mentioned
gen double eq_rsu_cnt_fh    = llm_n_rsu_mentioned
gen double eq_restr_cnt_fh  = llm_n_restricted_stock_mentioned
gen double eq_profit_cnt_fh = llm_n_profit_interest_mentioned
gen double eq_carry_cnt_fh  = llm_n_carried_interest_mentioned
gen double eq_phantom_cnt_fh = llm_n_phantom_equity_mentioned
gen double eq_espp_cnt_fh    = llm_n_espp_mentioned
gen double eq_esop_cnt_fh    = llm_n_esop_mentioned
gen double eq_sar_cnt_fh     = llm_n_stock_app_rights_ment
gen double eq_other_cnt_fh   = llm_n_other_equity_mentioned

foreach v in ///
    eq_opt_cnt_fh ///
    eq_rsu_cnt_fh ///
    eq_restr_cnt_fh ///
    eq_profit_cnt_fh ///
    eq_carry_cnt_fh ///
    eq_phantom_cnt_fh ///
    eq_espp_cnt_fh ///
    eq_esop_cnt_fh ///
    eq_sar_cnt_fh ///
    eq_other_cnt_fh {
    replace `v' = 0 if missing(`v')
    replace `v' = 0 if `v' < 0
}

* Shares among parse-ok postings (set to 0 if denominator is 0)
gen double eq_opt_share_fh = cond(llm_n_parse_ok > 0, eq_opt_cnt_fh / llm_n_parse_ok, 0)
gen double eq_rsu_share_fh = cond(llm_n_parse_ok > 0, eq_rsu_cnt_fh / llm_n_parse_ok, 0)
gen double eq_restr_share_fh = cond(llm_n_parse_ok > 0, eq_restr_cnt_fh / llm_n_parse_ok, 0)
gen double eq_profit_share_fh = cond(llm_n_parse_ok > 0, eq_profit_cnt_fh / llm_n_parse_ok, 0)
gen double eq_carry_share_fh = cond(llm_n_parse_ok > 0, eq_carry_cnt_fh / llm_n_parse_ok, 0)
gen double eq_phantom_share_fh = cond(llm_n_parse_ok > 0, eq_phantom_cnt_fh / llm_n_parse_ok, 0)
gen double eq_espp_share_fh    = cond(llm_n_parse_ok > 0, eq_espp_cnt_fh / llm_n_parse_ok, 0)
gen double eq_esop_share_fh    = cond(llm_n_parse_ok > 0, eq_esop_cnt_fh / llm_n_parse_ok, 0)
gen double eq_sar_share_fh     = cond(llm_n_parse_ok > 0, eq_sar_cnt_fh / llm_n_parse_ok, 0)
gen double eq_other_share_fh   = cond(llm_n_parse_ok > 0, eq_other_cnt_fh / llm_n_parse_ok, 0)

foreach v in ///
    eq_opt_share_fh ///
    eq_rsu_share_fh ///
    eq_restr_share_fh ///
    eq_profit_share_fh ///
    eq_carry_share_fh ///
    eq_phantom_share_fh ///
    eq_espp_share_fh ///
    eq_esop_share_fh ///
    eq_sar_share_fh ///
    eq_other_share_fh {
    replace `v' = 0 if missing(`v')
    replace `v' = 0 if `v' < 0 | `v' > 1
}

* Log-count transforms for type mentions
gen double eq_opt_log_fh    = ln(1 + eq_opt_cnt_fh)
gen double eq_rsu_log_fh    = ln(1 + eq_rsu_cnt_fh)
gen double eq_restr_log_fh  = ln(1 + eq_restr_cnt_fh)
gen double eq_profit_log_fh = ln(1 + eq_profit_cnt_fh)
gen double eq_carry_log_fh  = ln(1 + eq_carry_cnt_fh)
gen double eq_phantom_log_fh = ln(1 + eq_phantom_cnt_fh)
gen double eq_espp_log_fh    = ln(1 + eq_espp_cnt_fh)
gen double eq_esop_log_fh    = ln(1 + eq_esop_cnt_fh)
gen double eq_sar_log_fh     = ln(1 + eq_sar_cnt_fh)
gen double eq_other_log_fh   = ln(1 + eq_other_cnt_fh)

* Arcsin-sqrt transform for overall equity share
gen double eq_share_asin_fh = asin(sqrt(eq_share_fh))
replace eq_share_asin_fh = 0 if missing(eq_share_asin_fh)

* Firm-level summaries computed on unique firm×yh cells to avoid user-weighting
tempvar __tag_fy
egen byte `__tag_fy' = tag(firm_id yh)

* Firm-level "any equity" pre/post and "new offer" indicator
gen double __eq_any_pre_for_max  = eq_any_fh if `__tag_fy' == 1 & covid == 0
gen double __eq_any_post_for_max = eq_any_fh if `__tag_fy' == 1 & covid == 1
bysort firm_id: egen double eq_any_firm_pre  = max(__eq_any_pre_for_max)
bysort firm_id: egen double eq_any_firm_post = max(__eq_any_post_for_max)
replace eq_any_firm_pre  = 0 if missing(eq_any_firm_pre)
replace eq_any_firm_post = 0 if missing(eq_any_firm_post)
gen byte eq_any_firm_new = (eq_any_firm_pre == 0 & eq_any_firm_post == 1)
replace eq_any_firm_new = 0 if missing(eq_any_firm_new)
drop __eq_any_pre_for_max __eq_any_post_for_max

* Firm-level mean shares / logs by period (post, pre, and delta = post-pre)
foreach base in ///
    eq_share_fh ///
    eq_share_asin_fh ///
    eq_count_log_fh ///
    eq_opt_share_fh ///
    eq_rsu_share_fh ///
    eq_restr_share_fh ///
    eq_profit_share_fh ///
    eq_carry_share_fh ///
    eq_phantom_share_fh ///
    eq_espp_share_fh ///
    eq_esop_share_fh ///
    eq_sar_share_fh ///
    eq_other_share_fh ///
    eq_opt_log_fh ///
    eq_rsu_log_fh ///
    eq_restr_log_fh ///
    eq_profit_log_fh ///
    eq_carry_log_fh ///
    eq_phantom_log_fh ///
    eq_espp_log_fh ///
    eq_esop_log_fh ///
    eq_sar_log_fh ///
    eq_other_log_fh {

    gen double __`base'_post = `base' if `__tag_fy' == 1 & covid == 1
    gen double __`base'_pre  = `base' if `__tag_fy' == 1 & covid == 0
    bysort firm_id: egen double `base'_firm_post = mean(__`base'_post)
    bysort firm_id: egen double `base'_firm_pre  = mean(__`base'_pre)
    replace `base'_firm_post = 0 if missing(`base'_firm_post)
    replace `base'_firm_pre  = 0 if missing(`base'_firm_pre)
    gen double `base'_firm_delta = `base'_firm_post - `base'_firm_pre
    replace `base'_firm_delta = 0 if missing(`base'_firm_delta)
    drop __`base'_post __`base'_pre
}

* Median split / top-quintile indicators for overall post equity share
tempvar __tag_firm __tile_med __tile_qui
egen byte `__tag_firm' = tag(firm_id)
xtile `__tile_med' = eq_share_fh_firm_post if `__tag_firm' == 1, nq(2)
gen byte eq_share_post_med = (`__tile_med' == 2) if `__tag_firm' == 1
replace eq_share_post_med = 0 if missing(eq_share_post_med)
bysort firm_id: egen byte eq_share_post_med_all = max(eq_share_post_med)
drop eq_share_post_med
rename eq_share_post_med_all eq_share_post_med

xtile `__tile_qui' = eq_share_fh_firm_post if `__tag_firm' == 1, nq(5)
gen byte eq_share_post_topqui = (`__tile_qui' == 5) if `__tag_firm' == 1
replace eq_share_post_topqui = 0 if missing(eq_share_post_topqui)
bysort firm_id: egen byte eq_share_post_topqui_all = max(eq_share_post_topqui)
drop eq_share_post_topqui
rename eq_share_post_topqui_all eq_share_post_topqui
drop `__tile_med' `__tile_qui'

*------------------------------------------------------------*
* 3) Define control variants (all post-shift controls)
*------------------------------------------------------------*
* Baseline-type controls (for reference)
gen double z_eq_firm_any         = covid * eq_any_firm_post
gen double z_eq_firm_any_startup = covid * eq_any_firm_post * startup

gen double z_eq_firm_share_post         = covid * eq_share_fh_firm_post
gen double z_eq_firm_share_post_startup = covid * eq_share_fh_firm_post * startup

gen double z_eq_firm_share_med         = covid * eq_share_post_med
gen double z_eq_firm_share_med_startup = covid * eq_share_post_med * startup

gen double z_eq_firm_share_topq         = covid * eq_share_post_topqui
gen double z_eq_firm_share_topq_startup = covid * eq_share_post_topqui * startup

gen double z_eq_firm_share_delta         = covid * eq_share_fh_firm_delta
gen double z_eq_firm_share_delta_startup = covid * eq_share_fh_firm_delta * startup

gen double z_eq_firm_any_new         = covid * eq_any_firm_new
gen double z_eq_firm_any_new_startup = covid * eq_any_firm_new * startup

gen double z_eq_firm_countlog_post         = covid * eq_count_log_fh_firm_post
gen double z_eq_firm_countlog_post_startup = covid * eq_count_log_fh_firm_post * startup

gen double z_eq_firm_countlog_delta         = covid * eq_count_log_fh_firm_delta
gen double z_eq_firm_countlog_delta_startup = covid * eq_count_log_fh_firm_delta * startup

gen double z_asin_post    = covid * eq_share_asin_fh_firm_post
gen double z_asin_post_su = covid * eq_share_asin_fh_firm_post * startup

gen double z_asin_delta    = covid * eq_share_asin_fh_firm_delta
gen double z_asin_delta_su = covid * eq_share_asin_fh_firm_delta * startup

* Type-specific (stock options, RSU, restricted stock, profit interest, carried interest)
gen double z_opt_share_post         = covid * eq_opt_share_fh_firm_post
gen double z_opt_share_post_startup = covid * eq_opt_share_fh_firm_post * startup
gen double z_opt_share_delta         = covid * eq_opt_share_fh_firm_delta
gen double z_opt_share_delta_startup = covid * eq_opt_share_fh_firm_delta * startup
gen double z_opt_log_post         = covid * eq_opt_log_fh_firm_post
gen double z_opt_log_post_startup = covid * eq_opt_log_fh_firm_post * startup

gen double z_rsu_share_post         = covid * eq_rsu_share_fh_firm_post
gen double z_rsu_share_post_startup = covid * eq_rsu_share_fh_firm_post * startup
gen double z_rsu_log_post           = covid * eq_rsu_log_fh_firm_post
gen double z_rsu_log_post_startup   = covid * eq_rsu_log_fh_firm_post * startup

gen double z_restr_share_post         = covid * eq_restr_share_fh_firm_post
gen double z_restr_share_post_startup = covid * eq_restr_share_fh_firm_post * startup
gen double z_restr_log_post           = covid * eq_restr_log_fh_firm_post
gen double z_restr_log_post_startup   = covid * eq_restr_log_fh_firm_post * startup

gen double z_profit_share_post         = covid * eq_profit_share_fh_firm_post
gen double z_profit_share_post_startup = covid * eq_profit_share_fh_firm_post * startup
gen double z_profit_log_post           = covid * eq_profit_log_fh_firm_post
gen double z_profit_log_post_startup   = covid * eq_profit_log_fh_firm_post * startup

gen double z_carry_share_post         = covid * eq_carry_share_fh_firm_post
gen double z_carry_share_post_startup = covid * eq_carry_share_fh_firm_post * startup
gen double z_carry_log_post           = covid * eq_carry_log_fh_firm_post
gen double z_carry_log_post_startup   = covid * eq_carry_log_fh_firm_post * startup

gen double z_phantom_share_post         = covid * eq_phantom_share_fh_firm_post
gen double z_phantom_share_post_startup = covid * eq_phantom_share_fh_firm_post * startup
gen double z_phantom_log_post           = covid * eq_phantom_log_fh_firm_post
gen double z_phantom_log_post_startup   = covid * eq_phantom_log_fh_firm_post * startup

gen double z_espp_share_post         = covid * eq_espp_share_fh_firm_post
gen double z_espp_share_post_startup = covid * eq_espp_share_fh_firm_post * startup
gen double z_espp_log_post           = covid * eq_espp_log_fh_firm_post
gen double z_espp_log_post_startup   = covid * eq_espp_log_fh_firm_post * startup

gen double z_esop_share_post         = covid * eq_esop_share_fh_firm_post
gen double z_esop_share_post_startup = covid * eq_esop_share_fh_firm_post * startup
gen double z_esop_log_post           = covid * eq_esop_log_fh_firm_post
gen double z_esop_log_post_startup   = covid * eq_esop_log_fh_firm_post * startup

gen double z_sar_share_post         = covid * eq_sar_share_fh_firm_post
gen double z_sar_share_post_startup = covid * eq_sar_share_fh_firm_post * startup
gen double z_sar_log_post           = covid * eq_sar_log_fh_firm_post
gen double z_sar_log_post_startup   = covid * eq_sar_log_fh_firm_post * startup

gen double z_other_share_post         = covid * eq_other_share_fh_firm_post
gen double z_other_share_post_startup = covid * eq_other_share_fh_firm_post * startup
gen double z_other_log_post           = covid * eq_other_log_fh_firm_post
gen double z_other_log_post_startup   = covid * eq_other_log_fh_firm_post * startup

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
    eq_firm_any ///
    eq_firm_share_post ///
    eq_firm_share_ge_median ///
    eq_firm_share_top_quintile ///
    eq_firm_share_delta ///
    eq_firm_any_new ///
    eq_firm_countlog_post ///
    eq_firm_countlog_delta ///
    eq_firm_share_asin_post ///
    eq_firm_share_asin_delta ///
    opt_share_post ///
    opt_share_delta ///
    opt_log_post ///
    rsu_share_post ///
    rsu_log_post ///
    restr_share_post ///
    restr_log_post ///
    profit_share_post ///
    profit_log_post ///
    carry_share_post ///
    carry_log_post ///
    phantom_share_post ///
    phantom_log_post ///
    espp_share_post ///
    espp_log_post ///
    esop_share_post ///
    esop_log_post ///
    sar_share_post ///
    sar_log_post ///
    other_share_post ///
    other_log_post ///
    combo_restr_rsu ///
    combo_restr_opt ///
    combo_restr_rsu_opt

* Map spec variants → control varlists (baseline is empty)
* NOTE: local macro names must be <= 31 chars in Stata batch mode.
local ctl_baseline ""
local ctl_eq_firm_any                 "z_eq_firm_any z_eq_firm_any_startup"
local ctl_eq_firm_share_post          "z_eq_firm_share_post z_eq_firm_share_post_startup"
local ctl_eq_firm_share_ge_median     "z_eq_firm_share_med z_eq_firm_share_med_startup"
local ctl_eq_firm_share_top_quintile  "z_eq_firm_share_topq z_eq_firm_share_topq_startup"
local ctl_eq_firm_share_delta         "z_eq_firm_share_delta z_eq_firm_share_delta_startup"
local ctl_eq_firm_any_new             "z_eq_firm_any_new z_eq_firm_any_new_startup"
local ctl_eq_firm_countlog_post       "z_eq_firm_countlog_post z_eq_firm_countlog_post_startup"
local ctl_eq_firm_countlog_delta      "z_eq_firm_countlog_delta z_eq_firm_countlog_delta_startup"
local ctl_eq_firm_share_asin_post     "z_asin_post z_asin_post_su"
local ctl_eq_firm_share_asin_delta    "z_asin_delta z_asin_delta_su"

local ctl_opt_share_post              "z_opt_share_post z_opt_share_post_startup"
local ctl_opt_share_delta             "z_opt_share_delta z_opt_share_delta_startup"
local ctl_opt_log_post                "z_opt_log_post z_opt_log_post_startup"
local ctl_rsu_share_post              "z_rsu_share_post z_rsu_share_post_startup"
local ctl_rsu_log_post                "z_rsu_log_post z_rsu_log_post_startup"
local ctl_restr_share_post            "z_restr_share_post z_restr_share_post_startup"
local ctl_restr_log_post              "z_restr_log_post z_restr_log_post_startup"
local ctl_profit_share_post           "z_profit_share_post z_profit_share_post_startup"
local ctl_profit_log_post             "z_profit_log_post z_profit_log_post_startup"
local ctl_carry_share_post            "z_carry_share_post z_carry_share_post_startup"
local ctl_carry_log_post              "z_carry_log_post z_carry_log_post_startup"

local ctl_phantom_share_post          "z_phantom_share_post z_phantom_share_post_startup"
local ctl_phantom_log_post            "z_phantom_log_post z_phantom_log_post_startup"
local ctl_espp_share_post             "z_espp_share_post z_espp_share_post_startup"
local ctl_espp_log_post               "z_espp_log_post z_espp_log_post_startup"
local ctl_esop_share_post             "z_esop_share_post z_esop_share_post_startup"
local ctl_esop_log_post               "z_esop_log_post z_esop_log_post_startup"
local ctl_sar_share_post              "z_sar_share_post z_sar_share_post_startup"
local ctl_sar_log_post                "z_sar_log_post z_sar_log_post_startup"
local ctl_other_share_post            "z_other_share_post z_other_share_post_startup"
local ctl_other_log_post              "z_other_log_post z_other_log_post_startup"

* Multi-control combos (often closer in spirit to growth controls)
local ctl_combo_restr_rsu             "z_restr_share_post z_restr_share_post_startup z_rsu_log_post z_rsu_log_post_startup"
local ctl_combo_restr_opt             "z_restr_share_post z_restr_share_post_startup z_opt_log_post z_opt_log_post_startup"
local ctl_combo_restr_rsu_opt         "z_restr_share_post z_restr_share_post_startup z_rsu_log_post z_rsu_log_post_startup z_opt_log_post z_opt_log_post_startup"

foreach spec_variant of local spec_variants {
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
