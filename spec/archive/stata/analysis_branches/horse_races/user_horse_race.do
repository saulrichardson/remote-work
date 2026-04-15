*====================================================================*
*  user_horse_race.do
*  ------------------------------------------------------------------
*  Robustness / "horse race" specification (mechanism-style columns):
*    - Sequentially adds firm-level exposure controls based on occupation mix:
*        (i) Offshorability
*        (ii) GenAI exposure (total)
*        (iii) Both
*
*  This follows the same “add interacted controls across columns” pattern used
*  in the mechanism specs (e.g. spec/stata/user_mechanisms_with_growth.do):
*    - Exposures are time-invariant at the firm level
*    - Enter only as covid interactions (and covid×startup) so they remain
*      identified under firm FE
*    - Baseline is estimated on the full sample; horse-race columns are
*      estimated on the subsample with non-missing exposure measures
 *
 *  REQUIRED INPUTS
 *    - data/clean/user_panel_<variant>.dta, produced by:
 *        src/stata/build_all_user_panels.do
*    - data/clean/scoop_firm_horse_race.dta, produced by:
*        src/stata/build_firm_horse_race_scores.do
*
*  OUTPUTS
 *    - results/raw/user_horse_race_<variant>/consolidated_results.csv
 *====================================================================*

	args panel_variant
	if "`panel_variant'" == "" local panel_variant "precovid"
	local specname user_horse_race_`panel_variant'

// Bootstrap paths -----------------------------------------------------
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

	// Load panel ----------------------------------------------------------
	use "$processed_data/user_panel_`panel_variant'.dta", clear

// Fail loudly if horse-race inputs are missing ------------------------
capture confirm variable company_offshorability
if _rc != 0 {
    di as error "Missing company_offshorability. Rebuild the user panel after running:"
    di as error "  do src/stata/build_firm_horse_race_scores.do"
    di as error "  do src/stata/build_all_user_panels.do"
    exit 111
}
	capture confirm variable company_genai_total
	if _rc != 0 {
	    di as error "Missing company_genai_total. Rebuild the user panel after running:"
	    di as error "  do src/stata/build_firm_horse_race_scores.do"
	    di as error "  do src/stata/build_all_user_panels.do"
	    exit 111
	}

	// Output dir ----------------------------------------------------------
	local result_dir  "$results/`specname'"
	capture mkdir "`result_dir'"

	capture postclose handle
	tempfile out
	postfile handle ///
	    str8   model_type  ///  OLS / IV
	    str40  spec        ///  baseline / offshore / genai_total / offshore_genai_total
	    str40  param       ///  var3 / var5
	    double coef se pval pre_mean ///
	    double rkf nobs     ///
	    using `out', replace


	// FE/cluster (match baseline user_productivity.do) ---------------------
	local FE "absorb(user_id firm_id yh) vce(cluster user_id)"

	// Outcome + reporting mean ---------------------------------------------
	local y total_contributions_q100
	summarize `y' if covid == 0, meanonly
	local pre_mean = r(mean)

	// Interactions (kept local to this spec) ------------------------------
	gen hr_off_covid    = covid * company_offshorability
	gen hr_off_covid_s  = covid * company_offshorability * startup

	gen hr_genaiT_covid   = covid * company_genai_total
	gen hr_genaiT_covid_s = covid * company_genai_total * startup


	// ---------------------------------------------------------------------
	// Column 1: Baseline (full sample) ------------------------------------
	// ---------------------------------------------------------------------
	di as text "→ Spec: baseline (full sample)"

	reghdfe `y' var3 var5 var4, `FE'
	local N = e(N)
	foreach p in var3 var5 {
	    local b    = _b[`p']
	    local se   = _se[`p']
	    local t    = `b'/`se'
	    local pval = 2*ttail(e(df_r), abs(`t'))
	    post handle ("OLS") ("baseline") ("`p'") ///
	                    (`b') (`se') (`pval') (`pre_mean') ///
	                    (.) (`N')
	}

	ivreghdfe `y' (var3 var5 = var6 var7) var4, `FE' savefirst
	local rkf = e(rkf)
	local N   = e(N)
	foreach p in var3 var5 {
	    local b    = _b[`p']
	    local se   = _se[`p']
	    local t    = `b'/`se'
	    local pval = 2*ttail(e(df_r), abs(`t'))
	    post handle ("IV") ("baseline") ("`p'") ///
	                    (`b') (`se') (`pval') (`pre_mean') ///
	                    (`rkf') (`N')
	}

	// ---------------------------------------------------------------------
	// Restrict sample for horse-race columns (common sample) ---------------
	// ---------------------------------------------------------------------
	count if missing(company_offshorability) | missing(company_genai_total)
	di as text "→ Horse-race sample restriction: dropping " r(N) " obs with missing offshorability or GenAI exposure."
	drop if missing(company_offshorability) | missing(company_genai_total)


	// ---------------------------------------------------------------------
	// Column 2+: sequentially add interacted controls ----------------------
	// ---------------------------------------------------------------------
	local specs "offshore genai_total offshore_genai_total"

	foreach s of local specs {
	    di as text "→ Spec: `s'"

	    local EXOG "var4"
	    if "`s'" == "offshore" {
	        local EXOG "var4 hr_off_covid hr_off_covid_s"
	    }
	    else if "`s'" == "genai_total" {
	        local EXOG "var4 hr_genaiT_covid hr_genaiT_covid_s"
	    }
	    else if "`s'" == "offshore_genai_total" {
	        local EXOG "var4 hr_off_covid hr_off_covid_s hr_genaiT_covid hr_genaiT_covid_s"
	    }

	    // OLS -------------------------------------------------------------
	    reghdfe `y' var3 var5 `EXOG', `FE'
	    local N = e(N)
	    foreach p in var3 var5 {
	        local b    = _b[`p']
	        local se   = _se[`p']
	        local t    = `b'/`se'
	        local pval = 2*ttail(e(df_r), abs(`t'))
	        post handle ("OLS") ("`s'") ("`p'") ///
	                        (`b') (`se') (`pval') (`pre_mean') ///
	                        (.) (`N')
	    }

	    // IV --------------------------------------------------------------
	    ivreghdfe `y' (var3 var5 = var6 var7) `EXOG', `FE' savefirst
	    local rkf = e(rkf)
	    local N   = e(N)
	    foreach p in var3 var5 {
	        local b    = _b[`p']
	        local se   = _se[`p']
	        local t    = `b'/`se'
	        local pval = 2*ttail(e(df_r), abs(`t'))
	        post handle ("IV") ("`s'") ("`p'") ///
	                        (`b') (`se') (`pval') (`pre_mean') ///
	                        (`rkf') (`N')
	    }
	}

	postclose handle
	use `out', clear
	export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
log close
