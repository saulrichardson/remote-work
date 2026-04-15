*============================================================*
* user_productivity_stayer.do
* Runs the baseline user productivity spec on the boundary-stayer spell only:
* workers whose last pre-COVID firm equals their first post-COVID firm, keeping
* only the spell that spans that boundary (other spells for the same user are
* dropped). Estimates OLS and 2SLS with user, firm, and time FE.
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional variant argument *before* bootstrapping paths
* --------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_`panel_variant'_stayer

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

// 1a) Identify boundary spell for stayers
sort user_id y half
by user_id: egen pre_yh_max  = max(cond(covid==0, yh, .))
by user_id: egen post_yh_min = min(cond(covid==1, yh, .))

gen firm_pre_last   = firm_id if yh==pre_yh_max  & covid==0
gen firm_post_first = firm_id if yh==post_yh_min & covid==1
by user_id: egen firm_pre_last_u   = max(firm_pre_last)
by user_id: egen firm_post_first_u = max(firm_post_first)

// Spell IDs based on firm changes
by user_id (y half): gen byte firm_change = firm_id != firm_id[_n-1] if _n>1
replace firm_change = 0 if missing(firm_change)
by user_id: gen spell_id = sum(firm_change) + 1

// Spells containing the boundary observations
gen mark_pre  = yh==pre_yh_max  & covid==0
gen mark_post = yh==post_yh_min & covid==1
by user_id: egen spell_pre  = max(cond(mark_pre,  spell_id, .))
by user_id: egen spell_post = max(cond(mark_post, spell_id, .))

// Boundary stayer: same firm across boundary and both points in same spell
gen byte stayer_boundary = firm_pre_last_u==firm_post_first_u ///
    & firm_pre_last_u<. & firm_post_first_u<. ///
    & spell_pre==spell_post & spell_pre<.

// Keep only the spell that spans the boundary for stayers
keep if stayer_boundary & spell_id==spell_pre

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
    
// 3) Loop over outcomes (keep aligned with baseline)
local outcomes total_contributions_q100 
local fs_done 0

foreach y of local outcomes {
    di as text "→ Processing outcome: `y' (stayer sample)"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----- OLS ----- (firm × user match FE + time FE)
    reghdfe `y' var3 var5 var4, absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
        
    local N = e(N) 
    
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`N')
    }

    // ----- IV (2nd‐stage) -----
    ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
        
    local rkf = e(rkf)
    local N = e(N) 
    
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N')
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
