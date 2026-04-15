*======================================================================*
* user_productivity_csa_interactions.do
* Estimates the canonical user-productivity specification while
* allowing the remote-work effects (var3 / var5) to vary by CSA.
* The script keeps the top-N CSAs (default: 14), interacts the
* endogenous regressors and instruments with CSA dummies, and
* exports CSA-specific OLS and IV coefficients.
*======================================================================*

version 17
clear all
set more off

*---- Arguments -------------------------------------------------------*
args panel_variant max_rank
if "`panel_variant'" == "" local panel_variant "precovid"
if "`max_rank'" == "" local max_rank 14

local specname user_productivity_csa_interactions_`panel_variant'

*---- Bootstrap paths -------------------------------------------------*
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text



*---- Load panel ------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear


*---- Merge CSA mapping -----------------------------------------------*
local mapping_file "$PROJECT_ROOT/data/clean/csa_msa_top14_mapping.csv"
if !fileexists("`mapping_file'") {
    di as error "Mapping file missing: `mapping_file'"
    exit 601
}

tempfile csa_map
import delimited using "`mapping_file'", varnames(1) clear
rename cbsacode company_cbsacode
save `csa_map'

use "$processed_data/user_panel_`panel_variant'.dta", clear
capture confirm numeric variable company_cbsacode
if _rc {
    destring company_cbsacode, replace force
    capture confirm numeric variable company_cbsacode
    if _rc {
        di as error "company_cbsacode is not numeric even after destring."
        exit 459
    }
}

merge m:1 company_cbsacode using `csa_map', keep(master match) nogen
keep if csa_rank <= `max_rank'
drop if missing(csa_rank)

if _N == 0 {
    di as error "No observations remain after restricting to top `max_rank' CSAs."
    exit 2000
}

encode csa_name, gen(csa_id)
bys csa_id: egen csa_rank_id = min(csa_rank)

levelsof csa_id, local(csa_ids)
di as text "Estimating CSA-varying effects for `:word count `csa_ids'' CSAs (top `max_rank')."

*---- Build CSA-specific regressors -----------------------------------*
local regvars ""
foreach cid of local csa_ids {
    local stub = "csa`cid'"
    gen double rem_post_startup_`stub' = var5 * (csa_id == `cid')

    local regvars "`regvars' rem_post_startup_`stub'"
}

*---- Prep result containers ------------------------------------------*
local result_dir "$RAW_RESULTS/`specname'"
capture mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str8   model_type ///
    str40  outcome ///
    str6   param ///
    str80  csa_name ///
    double csa_rank ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local outcomes total_contributions_q100

foreach y of local outcomes {
    di as text "→ Outcome: `y'"
    quietly summarize `y' if covid == 0
    local pre_mean = r(mean)

    *----- OLS --------------------------------------------------------*
    reghdfe `y' `regvars' var4, absorb(user_id firm_id yh) vce(cluster user_id)
    local N = e(N)

    foreach cid of local csa_ids {
        local stub = "csa`cid'"
        local cname : label (csa_id) `cid'
        quietly summarize csa_rank_id if csa_id == `cid'
        local crank = r(min)

        local param = "rem_post_startup_`stub'"
        local coef = _b[`param']
        local se   = _se[`param']
        local t    = `coef'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("var5") ("`cname'") ///
            (`crank') (`coef') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }
}

postclose handle
use `out', clear
sort model_type param csa_rank
export delimited using "`result_dir'/consolidated_results_by_csa.csv", ///
    replace delimiter(",") quote

di as result "✓ Wrote CSA-specific results → `result_dir'/consolidated_results_by_csa.csv"
capture log close
