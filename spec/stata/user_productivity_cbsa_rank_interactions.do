*============================================================*
* user_productivity_cbsa_rank_interactions.do
* Variant of the baseline user-productivity spec that augments the
* canonical regressors (var3 / var5 / var4) with interactions between
* those terms and the worker CBSA rank derived from the top-MSA list.
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional variant argument *before* bootstrapping paths -----------
* --------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_cbsa_rank_interactions_`panel_variant'

// 0) Setup environment
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



// 1) Load worker‐level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear


capture confirm numeric variable cbsacode
if _rc {
    destring cbsacode, replace force
    capture confirm numeric variable cbsacode
    if _rc {
        di as error "Panel must contain numeric cbsacode."
        exit 459
    }
}
drop if missing(cbsacode)

local rank_csv "$PROJECT_ROOT/data/clean/top_msas_`panel_variant'.csv"
if !fileexists("`rank_csv'") {
    di as error "Missing ranked CBSA list: `rank_csv'"
    exit 601
}

tempfile worker_ranks
preserve
    import delimited using "`rank_csv'", varnames(1) clear
    keep cbsacode msa_rank
    destring cbsacode, replace force
    drop if missing(cbsacode)
    save `worker_ranks'
restore

merge m:1 cbsacode using `worker_ranks', keep(match) nogen
if _N == 0 {
    di as error "No observations remain after merging worker CBSA ranks."
    exit 2000
}

capture confirm numeric variable msa_rank
if _rc {
    destring msa_rank, replace force
}

summarize msa_rank, meanonly
local max_rank = r(max)
gen double msa_rank_desc = `max_rank' - msa_rank + 1

gen double var3_rank = var3 * msa_rank_desc
gen double var5_rank = var5 * msa_rank_desc
gen double var4_rank = var4 * msa_rank_desc
gen double var6_rank = var6 * msa_rank_desc
gen double var7_rank = var7 * msa_rank_desc

drop _merge
local result_dir  "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
*--- postfile header (main results) -------------------------------------------
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

*------------------------------------------------------------------
*  First-stage results → first_stage_fstats.csv
*------------------------------------------------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace
	
// 3) Loop over outcomes
// Include percentile-rank and Winsorized versions of the contribution
// measures
local outcomes total_contributions_q100 
local fs_done 0
local reg_params "var3 var5 var4 var3_rank var5_rank var4_rank"
local endog_params "var3 var5 var3_rank var5_rank"
local exog_only "var4 var4_rank"
local inst_params "var6 var7 var6_rank var7_rank"

foreach y of local outcomes {
    di as text "→ Processing outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----- OLS -----
    reghdfe `y' `reg_params', absorb(user_id firm_id yh) ///
        vce(cluster user_id)
		
	local N = e(N) 

    foreach p in `reg_params' {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
		*--- inside the OLS loop ------------------------------------------------------
        post handle ("OLS") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')                 // dot for rkf, then nobs
    }

    // ----- IV (2nd‐stage) -----
    ivreghdfe ///
        `y' (`endog_params' = `inst_params') `exog_only', ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
		
    local rkf = e(rkf)
	local N = e(N) 

    foreach p in `reg_params' {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
		*--- inside the IV loop -------------------------------------------------------
        post handle ("IV") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')            // rkf, then nobs
    }

	if !`fs_done' {
		matrix FS = e(first)
		local col = 1
		foreach endog of local endog_params {
			local Fval = FS[4,`col']
			estimates restore _ivreg2_`endog'
			local N_fs = e(N)
			foreach p in `inst_params' `exog_only' {
				local b    = _b[`p']
				local se   = _se[`p']
				local t    = `b'/`se'
				local pval = 2*ttail(e(df_r), abs(`t'))
				post handle_fs ("`endog'") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`Fval') (`rkf') (`N_fs')
			}
			local col = `col' + 1
		}
		local fs_done 1
	}
}

// 4) Close & export to CSV
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

* --- write first-stage CSV -----------------------------------------
postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
        replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
capture log close
