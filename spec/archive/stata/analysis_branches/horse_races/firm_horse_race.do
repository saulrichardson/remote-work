*====================================================================*
*  firm_horse_race.do
*  ------------------------------------------------------------------
*  Firm-level "horse race" robustness (mechanism-style columns) for
*  growth/join/leave outcomes:
*    - Sequentially adds firm-level occupation-mix exposure controls:
*        (i) Offshorability
*        (ii) GenAI exposure (total)
*        (iii) Both
*
*  Mirrors the interacted-controls procedure used in the mechanism specs:
*    - Exposures are time-invariant at the firm level
*    - Enter only as covid interactions (and covid×startup) due to firm FE
*    - Baseline is estimated on the full sample; horse-race columns are
*      estimated on the subsample with non-missing exposure measures
 *
 *  REQUIRED INPUTS
 *    - data/clean/firm_panel.dta, produced by src/stata/build_firm_panel.do
 *      (which merges in data/clean/scoop_firm_horse_race.dta)
*
*  OUTPUTS
*    - results/raw/firm_horse_race/consolidated_results.csv
*====================================================================*

// Bootstrap paths -----------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

// Load panel ----------------------------------------------------------
use "$processed_data/firm_panel.dta", clear

// Fail loudly if horse-race inputs are missing ------------------------
capture confirm variable offshorability
if _rc != 0 {
    di as error "Missing offshorability. Rebuild the firm panel after running:"
    di as error "  do src/stata/build_firm_horse_race_scores.do"
    di as error "  do src/stata/build_firm_panel.do"
    exit 111
}
capture confirm variable genai_total
if _rc != 0 {
    di as error "Missing genai_total. Rebuild the firm panel after running:"
    di as error "  do src/stata/build_firm_horse_race_scores.do"
    di as error "  do src/stata/build_firm_panel.do"
    exit 111
}

// Logging --------------------------------------------------------------
local specname "firm_horse_race"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

	// Interactions ---------------------------------------------------------
	gen hr_off_covid    = covid * offshorability
	gen hr_off_covid_s  = covid * offshorability * startup

	gen hr_genaiT_covid   = covid * genai_total
	gen hr_genaiT_covid_s = covid * genai_total * startup

// Output dir ----------------------------------------------------------
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

	capture postclose handle
	tempfile out
	postfile handle ///
	    str8   model_type  ///  OLS / IV
	    str40  spec        ///  baseline / offshore / genai_total / offshore_genai_total
	    str40  outcome     ///
	    str40  param       ///  var3 / var5
	    double coef se pval pre_mean ///
	    double rkf nobs     ///
	    using `out', replace

// Outcomes -------------------------------------------------------------
local outcome_vars growth_rate_we join_rate_we leave_rate_we

	foreach y of local outcome_vars {
	    di as text "→ Outcome: `y'"

	    summarize `y' if covid == 0, meanonly
	    local pre_mean = r(mean)

	    // -----------------------------------------------------------------
	    // Column 1: Baseline (full sample) --------------------------------
	    // -----------------------------------------------------------------
	    di as text "  → Spec: baseline (full sample)"

	    reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
	    local N = e(N)
	    foreach p in var3 var5 {
	        local b    = _b[`p']
	        local se   = _se[`p']
	        local t    = `b'/`se'
	        local pval = 2*ttail(e(df_r), abs(`t'))
	        post handle ("OLS") ("baseline") ("`y'") ("`p'") ///
	                        (`b') (`se') (`pval') (`pre_mean') ///
	                        (.) (`N')
	    }

	    ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
	        absorb(firm_id yh) vce(cluster firm_id) savefirst
	    local rkf = e(rkf)
	    local N   = e(N)
	    foreach p in var3 var5 {
	        local b    = _b[`p']
	        local se   = _se[`p']
	        local t    = `b'/`se'
	        local pval = 2*ttail(e(df_r), abs(`t'))
	        post handle ("IV") ("baseline") ("`y'") ("`p'") ///
	                        (`b') (`se') (`pval') (`pre_mean') ///
	                        (`rkf') (`N')
	    }

	    // -----------------------------------------------------------------
	    // Horse-race columns on common restricted sample -------------------
	    // -----------------------------------------------------------------
	    preserve
	        count if missing(offshorability) | missing(genai_total)
	        di as text "  → Horse-race restriction: dropping " r(N) " obs with missing offshorability or GenAI exposure."
	        drop if missing(offshorability) | missing(genai_total)

	        local specs "offshore genai_total offshore_genai_total"

	        foreach s of local specs {
	            di as text "  → Spec: `s'"

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

	            // OLS -----------------------------------------------------
	            reghdfe `y' var3 var5 `EXOG', absorb(firm_id yh) vce(cluster firm_id)
	            local N = e(N)
	            foreach p in var3 var5 {
	                local b    = _b[`p']
	                local se   = _se[`p']
	                local t    = `b'/`se'
	                local pval = 2*ttail(e(df_r), abs(`t'))
	                post handle ("OLS") ("`s'") ("`y'") ("`p'") ///
	                                (`b') (`se') (`pval') (`pre_mean') ///
	                                (.) (`N')
	            }

	            // IV ------------------------------------------------------
	            ivreghdfe `y' (var3 var5 = var6 var7) `EXOG', ///
	                absorb(firm_id yh) vce(cluster firm_id) savefirst
	            local rkf = e(rkf)
	            local N   = e(N)
	            foreach p in var3 var5 {
	                local b    = _b[`p']
	                local se   = _se[`p']
	                local t    = `b'/`se'
	                local pval = 2*ttail(e(df_r), abs(`t'))
	                post handle ("IV") ("`s'") ("`y'") ("`p'") ///
	                                (`b') (`se') (`pval') (`pre_mean') ///
	                                (`rkf') (`N')
	            }
	        }
	    restore
	}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
log close
