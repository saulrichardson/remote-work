*============================================================*
* user_productivity_llm_equity_restr_robustness.do
*
* Goal:
*   Targeted robustness checks for the restricted-stock mechanism results:
*     1) add public×post and public×post×startup controls;
*     2) re-run after excluding the firms with the largest restricted-control
*        support in the user-panel estimation universe.
*
* Output:
*   results/raw/user_productivity_llm_equity_restr_robustness_<panel_variant>/
*       consolidated_results.csv
*       top_restricted_firms.csv
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

local specname "user_productivity_llm_equity_restr_robustness_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

*------------------------------------------------------------*
* 1) Build firm_id×yh LLM merge (same name-key logic as the sweep)
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
    gen double llm_n_stock_app_rights_ment = 0
}

keep firm_id_key yh ///
    llm_n_parse_ok ///
    llm_n_restricted_stock_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_stock_options_mentioned

rename firm_id_key __firm_name_key
rename yh __yh_key
foreach v in ///
    llm_n_parse_ok ///
    llm_n_restricted_stock_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_stock_options_mentioned {
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
    llm_n_restricted_stock_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_stock_options_mentioned
duplicates drop firm_id yh, force
save `llm_by_firm', replace

*------------------------------------------------------------*
* 2) Load user panel and attach restricted / RSU / option measures
*------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 firm_id yh using `llm_by_firm', keep(master match) nogen

foreach v in ///
    llm_n_parse_ok ///
    llm_n_restricted_stock_mentioned ///
    llm_n_rsu_mentioned ///
    llm_n_stock_options_mentioned {
    replace `v' = 0 if missing(`v')
    replace `v' = 0 if `v' < 0
}

replace public = 0 if missing(public)
replace startup = 0 if missing(startup)

gen double eq_restr_share_fh = cond(llm_n_parse_ok > 0, llm_n_restricted_stock_mentioned / llm_n_parse_ok, 0)
replace eq_restr_share_fh = 0 if missing(eq_restr_share_fh) | eq_restr_share_fh < 0 | eq_restr_share_fh > 1

gen double eq_restr_log_fh = ln(1 + llm_n_restricted_stock_mentioned)
gen double eq_rsu_log_fh   = ln(1 + llm_n_rsu_mentioned)
gen double eq_opt_log_fh   = ln(1 + llm_n_stock_options_mentioned)

* Unique firm×yh cells for firm-level post means
tempvar __tag_fy
egen byte `__tag_fy' = tag(firm_id yh)

foreach base in eq_restr_share_fh eq_restr_log_fh eq_rsu_log_fh eq_opt_log_fh {
    gen double __`base'_post = `base' if `__tag_fy' == 1 & covid == 1
    bysort firm_id: egen double `base'_firm_post = mean(__`base'_post)
    replace `base'_firm_post = 0 if missing(`base'_firm_post)
    drop __`base'_post
}

*------------------------------------------------------------*
* 3) Controls and top-firm diagnostics
*------------------------------------------------------------*
gen double z_public_post         = covid * public
gen double z_public_post_startup = covid * public * startup

gen double z_restr_share_post         = covid * eq_restr_share_fh_firm_post
gen double z_restr_share_post_startup = covid * eq_restr_share_fh_firm_post * startup
gen double z_restr_log_post           = covid * eq_restr_log_fh_firm_post
gen double z_restr_log_post_startup   = covid * eq_restr_log_fh_firm_post * startup
gen double z_rsu_log_post             = covid * eq_rsu_log_fh_firm_post
gen double z_rsu_log_post_startup     = covid * eq_rsu_log_fh_firm_post * startup
gen double z_opt_log_post             = covid * eq_opt_log_fh_firm_post
gen double z_opt_log_post_startup     = covid * eq_opt_log_fh_firm_post * startup

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

preserve
keep if covid == 1 & eq_restr_share_fh_firm_post > 0
collapse (count) support_obs = user_id ///
         (firstnm) public startup ///
         (firstnm) restr_share_post = eq_restr_share_fh_firm_post ///
         (firstnm) restr_log_post = eq_restr_log_fh_firm_post ///
         (firstnm) rsu_log_post = eq_rsu_log_fh_firm_post ///
         (firstnm) opt_log_post = eq_opt_log_fh_firm_post, by(firm_id companyname)
gsort -support_obs companyname
gen rank = _n
order rank firm_id companyname support_obs public startup restr_share_post restr_log_post rsu_log_post opt_log_post
export delimited using "`result_dir'/top_restricted_firms.csv", replace delimiter(",") quote

local drop_top1_ids ""
local drop_top2_ids ""
local drop_top5_ids ""
levelsof firm_id if rank <= 1, local(drop_top1_ids)
levelsof firm_id if rank <= 2, local(drop_top2_ids)
levelsof firm_id if rank <= 5, local(drop_top5_ids)

local drop_top1_names ""
local drop_top2_names ""
local drop_top5_names ""
levelsof companyname if rank <= 1, local(drop_top1_names) clean
levelsof companyname if rank <= 2, local(drop_top2_names) clean
levelsof companyname if rank <= 5, local(drop_top5_names) clean
restore

di as text "Restricted-support top 1 firms: `drop_top1_names'"
di as text "Restricted-support top 2 firms: `drop_top2_names'"
di as text "Restricted-support top 5 firms: `drop_top5_names'"

gen byte __drop_top1 = 0
foreach __id of local drop_top1_ids {
    replace __drop_top1 = 1 if firm_id == `__id'
}

gen byte __drop_top2 = 0
foreach __id of local drop_top2_ids {
    replace __drop_top2 = 1 if firm_id == `__id'
}

gen byte __drop_top5 = 0
foreach __id of local drop_top5_ids {
    replace __drop_top5 = 1 if firm_id == `__id'
}

*------------------------------------------------------------*
* 4) Regression loop
*------------------------------------------------------------*
local outcome "total_contributions_q100"
summarize `outcome' if covid == 0, meanonly
local pre_mean = r(mean)

local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"

capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str16 sample_mode ///
    str40 spec_variant ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    double support_obs support_users support_firms ///
    using `out', replace

local spec_variants ///
    baseline ///
    public_only ///
    restr_share_post ///
    restr_share_post_public ///
    restr_log_post ///
    restr_log_post_public ///
    combo_restr_opt ///
    combo_restr_opt_public ///
    combo_restr_rsu_opt ///
    combo_restr_rsu_opt_public

local ctl_baseline ""
local ctl_public_only            "z_public_post z_public_post_startup"
local ctl_restr_share_post       "z_restr_share_post z_restr_share_post_startup"
local ctl_restr_share_post_public "z_restr_share_post z_restr_share_post_startup z_public_post z_public_post_startup"
local ctl_restr_log_post         "z_restr_log_post z_restr_log_post_startup"
local ctl_restr_log_post_public  "z_restr_log_post z_restr_log_post_startup z_public_post z_public_post_startup"
local ctl_combo_restr_opt        "z_restr_share_post z_restr_share_post_startup z_opt_log_post z_opt_log_post_startup"
local ctl_combo_restr_opt_public "z_restr_share_post z_restr_share_post_startup z_opt_log_post z_opt_log_post_startup z_public_post z_public_post_startup"
local ctl_combo_restr_rsu_opt    "z_restr_share_post z_restr_share_post_startup z_rsu_log_post z_rsu_log_post_startup z_opt_log_post z_opt_log_post_startup"
local ctl_combo_restr_rsu_opt_public "z_restr_share_post z_restr_share_post_startup z_rsu_log_post z_rsu_log_post_startup z_opt_log_post z_opt_log_post_startup z_public_post z_public_post_startup"

local sample_modes "all no_top1 no_top2 no_top5"
foreach sample_mode of local sample_modes {
    local sample_if "1"
    if "`sample_mode'" == "no_top1" local sample_if "__drop_top1 == 0"
    else if "`sample_mode'" == "no_top2" local sample_if "__drop_top2 == 0"
    else if "`sample_mode'" == "no_top5" local sample_if "__drop_top5 == 0"

    preserve
    keep if `sample_if' & covid == 1 & eq_restr_share_fh_firm_post > 0
    local support_obs = _N
    tempvar __tag_user __tag_firm
    egen byte `__tag_user' = tag(user_id)
    egen byte `__tag_firm' = tag(firm_id)
    quietly count if `__tag_user'
    local support_users = r(N)
    quietly count if `__tag_firm'
    local support_firms = r(N)
    restore

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

        capture quietly reghdfe `outcome' `ols_rhs' if `sample_if', `FE'
        if !_rc {
            local nobs = e(N)
            foreach p in var3 var5 {
                local b  = _b[`p']
                local se = _se[`p']
                local pval = .
                if `se' < . & `se' != 0 & e(df_r) < . {
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                }
                post handle ("OLS") ("`sample_mode'") ("`spec_variant'") ("`outcome'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (.) (`nobs') ///
                    (`support_obs') (`support_users') (`support_firms')
            }
        }

        capture quietly ivreghdfe `outcome' (`iv_endo' = `iv_inst') `iv_exog' if `sample_if', `FE'
        if !_rc {
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
                post handle ("IV") ("`sample_mode'") ("`spec_variant'") ("`outcome'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') (`rkf') (`nobs') ///
                    (`support_obs') (`support_users') (`support_firms')
            }
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
di as result "→ CSV : `result_dir'/consolidated_results.csv"
capture log close
