*============================================================*
*  user_productivity_initial.do
*  — Baseline spec (no startup × remote interaction) for worker
*    productivity.  Accepts *optional* first argument selecting the user
*    panel variant (unbalanced | balanced | precovid).  Default = unbalanced.
*    Example: do user_productivity_initial.do balanced
*============================================================*

* Parse variant argument ----------------------------------------------------
args variant
if "`variant'" == "" local variant "unbalanced"
global user_panel_variant "`variant'"
local specname user_productivity_initial_$user_panel_variant
capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

// 0) Setup environment
do "../src/globals.do"

// 1) Load worker‐level panel
use "$processed_data/user_panel_${user_panel_variant}.dta", clear

// 2) Prepare output dir & reset any old postfile
*--------------------------------------------------------------------------*
* Output directory is *always* suffixed with the panel variant so each run is
* explicit about the underlying sample (e.g., "user_productivity_initial_balanced").
*--------------------------------------------------------------------------*

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
    str8   endovar            ///
    str40  param              /// 
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace
	
// 3) Loop over outcomes
local outcomes total_contributions_q100 
local fs_done 0

foreach y of local outcomes {
    di as text "→ Processing outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----- OLS -----
    reghdfe `y' var3 var4, absorb(user_id firm_id yh) ///
        vce(cluster user_id)
		
	local N = e(N) 
	
    foreach p in var3 var4 {
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
        `y' (var3 = var6) var4, ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
		
    local rkf = e(rkf)
	local N = e(N) 
	
    foreach p in var3 var4 {
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
        local F3 = FS[4,1]

		/* -------- var3 first stage -------------------------------- */
		estimates restore _ivreg2_var3
		local N_fs = e(N)
		foreach p in var6 var4 {
			local b    = _b[`p']
			local se   = _se[`p']
			local t    = `b'/`se'
			local pval = 2*ttail(e(df_r), abs(`t'))

			post handle_fs ("var3") ("`p'") ///
							(`b') (`se') (`pval') ///
							(`F3') (`rkf') (`N_fs')
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
