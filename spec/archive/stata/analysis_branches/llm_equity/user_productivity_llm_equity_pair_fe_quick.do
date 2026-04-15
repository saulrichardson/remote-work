*============================================================*
* user_productivity_llm_equity_pair_fe_quick.do
*
* Quick FE sensitivity check requested by PI:
*   - baseline FE: absorb(user_id firm_id yh)
*   - pair FE:     absorb(firm_id#user_id yh)
*
* Output:
*   results/raw/user_productivity_llm_equity_pair_fe_quick_<panel>/consolidated_results.csv
*============================================================*

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

* Note: this script is a FE-structure robustness check for the core user spec.
* It does not use the enriched LLM equity panel; the second argument is ignored.

local specname "user_productivity_llm_equity_pair_fe_quick_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

tempfile panel_all

use "$processed_data/user_panel_`panel_variant'.dta", clear
save `panel_all', replace

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str16 fe_variant ///
    str8  model_type ///
    str40 outcome ///
    str40 param ///
    double coef se pval pre_mean ///
    double rkf nobs sample_n n_firms n_users ///
    using `out', replace

local outcomes "total_contributions_q100"
local fe_variants "baseline_fe pair_fe"

foreach fev of local fe_variants {
    use `panel_all', clear
    quietly count
    local sample_n = r(N)
    if `sample_n' == 0 continue

    local FE "absorb(user_id firm_id yh) vce(cluster user_id)"
    if "`fev'" == "pair_fe" {
        local FE "absorb(firm_id#user_id yh) vce(cluster user_id)"
    }

    tempvar __tag_firm __tag_user
    quietly egen `__tag_firm' = tag(firm_id)
    quietly count if `__tag_firm' == 1
    local n_firms = r(N)
    quietly egen `__tag_user' = tag(user_id)
    quietly count if `__tag_user' == 1
    local n_users = r(N)

    foreach y of local outcomes {
        quietly summarize `y' if covid == 0, meanonly
        local pre_mean = r(mean)
        local params "var3 var5"

        capture noisily reghdfe `y' ///
            var3 var5 var4, ///
            `FE'
        if !_rc {
            local nobs = e(N)
            foreach p of local params {
                capture local b = _b[`p']
                if _rc continue
                capture local se = _se[`p']
                if _rc continue
                local pval = .
                if (`se' == 0 | missing(`se')) {
                    local b = .
                    local se = .
                }
                else if `se' < . & e(df_r) < . {
                    local t = `b' / `se'
                    local pval = 2 * ttail(e(df_r), abs(`t'))
                }
                post handle ("`fev'") ("OLS") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }

        capture noisily ivreghdfe `y' ///
            (var3 var5 = var6 var7) ///
            var4, ///
            `FE'
        if !_rc {
            local nobs = e(N)
            local rkf = .
            capture local rkf = e(rkf)
            foreach p of local params {
                capture local b = _b[`p']
                if _rc continue
                capture local se = _se[`p']
                if _rc continue
                local pval = .
                if (`se' == 0 | missing(`se')) {
                    local b = .
                    local se = .
                }
                else if `se' < . & e(df_r) < . {
                    local t = `b' / `se'
                    local pval = 2 * ttail(e(df_r), abs(`t'))
                }
                post handle ("`fev'") ("IV") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`nobs') (`sample_n') (`n_firms') (`n_users')
            }
        }
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV : `result_dir'/consolidated_results.csv"
capture log close
