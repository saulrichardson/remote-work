*======================================================================*
* user_productivity_msa_interactions_firm.do
* Mirrors the worker-based MSA interactions but uses firm CBSA codes
* to identify the top-N MSAs by employment and interact the remote
* treatment with firm geography.
*======================================================================*

version 17
clear all
set more off

*---- Arguments -------------------------------------------------------*
args panel_variant top_n rank_half
if "`panel_variant'" == "" local panel_variant "precovid"
if "`top_n'" == ""        local top_n 30
if "`rank_half'" == ""    local rank_half "2019h2"

local specname user_productivity_msa_interactions_firm_`panel_variant'

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


capture confirm numeric variable company_cbsacode
if _rc {
    destring company_cbsacode, replace force
    capture confirm numeric variable company_cbsacode
    if _rc {
        di as error "Panel must contain numeric company_cbsacode."
        exit 459
    }
}
drop if missing(company_cbsacode)

capture confirm variable var5
if _rc {
    di as error "Missing var5 in panel."
    exit 111
}

*---- Import firm-based top-MSA list ----------------------------------*
local msa_list "$PROJECT_ROOT/data/clean/top_msas_firm_`panel_variant'.csv"
if !fileexists("`msa_list'") {
    di as error "Top-MSA list missing: `msa_list'. Run the firm Python builder first."
    exit 601
}

tempfile top_msas
preserve
    import delimited using "`msa_list'", varnames(1) clear
    keep company_cbsacode msa_name msa_rank
    save `top_msas'
restore

merge m:1 company_cbsacode using `top_msas', keep(match) nogen
if _N == 0 {
    di as error "No observations remain after merging firm-based top MSAs."
    exit 2000
}

capture confirm variable msa_group_id
if !_rc drop msa_group_id
encode msa_name, gen(msa_group_id)

levelsof msa_group_id, local(msa_ids)
di as text "Estimating MSA-varying effects for `:word count `msa_ids'' MSAs (top `top_n')."

*---- Build MSA-specific regressors -----------------------------------*
local regvars ""
foreach mid of local msa_ids {
    local stub = "msa`mid'"
    gen double rem_post_startup_`stub' = var5 * (msa_group_id == `mid')
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
    str80  msa_name ///
    double msa_rank ///
    double coef se pval pre_mean ///
    double rkf nobs ///
    using `out', replace

local outcomes total_contributions_q100

foreach y of local outcomes {
    di as text "→ Outcome: `y'"
    quietly summarize `y' if covid == 0
    local pre_mean = r(mean)

    reghdfe `y' `regvars' var4, absorb(user_id firm_id yh) vce(cluster user_id)
    local N = e(N)

    foreach mid of local msa_ids {
        local stub = "msa`mid'"
        local mname : label (msa_group_id) `mid'
        quietly summarize msa_rank if msa_group_id == `mid'
        local drank = r(min)

        local param = "rem_post_startup_`stub'"
        local coef = _b[`param']
        local se   = _se[`param']
        local t    = `coef'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("var5") ("`mname'") ///
            (`drank') (`coef') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }
}

postclose handle
use `out', clear
sort model_type param msa_rank
export delimited using "`result_dir'/consolidated_results_by_msa.csv", ///
    replace delimiter(",") quote

di as result "✓ Wrote firm-based MSA results → `result_dir'/consolidated_results_by_msa.csv"
capture log close
