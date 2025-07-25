*============================================================*
*  user_productivity.do
*  — Export OLS, IV and first‐stage results for worker productivity
*    OUTCOME.  The *first* (optional) command-line argument selects the user
*    panel variant:  unbalanced | balanced | precovid  (default = unbalanced)
*    This avoids reliance on pre-existing globals and makes driver scripts
*    more robust.
*    Example:   do user_productivity.do balanced
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional variant argument *before* sourcing globals --------------
* --------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_`panel_variant'
capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

// 0) Setup environment
do "../src/globals.do"

// 1) Load worker‐level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear


drop _merge


gen companyname_c = lower(companyname)
preserve
    import delimited "$processed_data/firm_hhi_msa.csv", clear
    rename companyname companyname_c     // lower-case key
tempfile hhi
save    `hhi'


restore

merge m:1 companyname_c using `hhi', keep(match) nogen



// preserve 
// import delimited using "/Users/saul/Downloads/Skills_match_k7.csv", clear
// tempfile teleclean1
// save    `teleclean1'
// restore
//
// merge m:1 companyname using  `teleclean1'
// drop _merge
//
//
// preserve 
// import delimited using "/Users/saul/Downloads/Skills_match_k1000.csv", clear
// tempfile teleclean2
// save    `teleclean2'
// restore
// merge m:1 companyname using  `teleclean2', force
// drop _merge



xtile lg_metric1_k7 = metric1_k7, nq(2)
xtile lg_metric2_k7 = metric2_k7, nq(2)
xtile lg_metric1_k1000 = metric1_k1000, nq(2)
xtile lg_metric2_k1000 = metric2_k1000, nq(2)



// 2) Prepare output dir & reset any old postfile
*--------------------------------------------------------------------------*
* Results are now *always* written to <specname> _<panel‐variant> (e.g.,
*   "user_productivity_unbalanced") so the output folder unambiguously states
* which user‐panel sample was used.  No silent fallback for the default
* sample.
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
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace
	
// 3) Loop over outcomes
// Include percentile-rank and Winsorized versions of the contribution
// measures
local outcomes total_contributions_q100 
// restricted_contributions_q100 total_contributions_we restricted_contributions_we
local fs_done 0

foreach y of local outcomes {
    di as text "→ Processing outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----- OLS -----
    reghdfe `y' var3 var5 var4, absorb(user_id firm_id yh) ///
        vce(cluster user_id)
		
	local N = e(N) 
	
    foreach p in var3 var5 var4 {
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
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
		
    local rkf = e(rkf)
	local N = e(N) 
	
    foreach p in var3 var5 var4 {
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
        local F5 = FS[4,2]

		/* -------- var3 first stage -------------------------------- */
		estimates restore _ivreg2_var3
		local N_fs = e(N)
		foreach p in var6 var7 var4 {
			local b    = _b[`p']
			local se   = _se[`p']
			local t    = `b'/`se'
			local pval = 2*ttail(e(df_r), abs(`t'))

			post handle_fs ("var3") ("`p'") ///
							(`b') (`se') (`pval') ///
							(`F3') (`rkf') (`N_fs')
		}

		/* -------- var5 first stage -------------------------------- */
		estimates restore _ivreg2_var5
		local N_fs = e(N)
		foreach p in var6 var7 var4 {
			local b    = _b[`p']
			local se   = _se[`p']
			local t    = `b'/`se'
			local pval = 2*ttail(e(df_r), abs(`t'))

			post handle_fs ("var5") ("`p'") ///
							(`b') (`se') (`pval') ///
							(`F5') (`rkf') (`N_fs')
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
