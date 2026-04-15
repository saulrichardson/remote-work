*============================================================*
*  firm_scaling_location_hhi.do
*  — Location concentration outcomes (HHI-based) using main firm_scaling spec
*============================================================*

// 0) Setup environment
// Hardcode project root so the legacy spec runs even when paths are mis-set
global PROJECT_ROOT "/Users/saulrichardson/Library/CloudStorage/Dropbox/Remote Work Startups/main"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



// Hardcode key directories so the spec runs even if global propagation breaks
global processed_data "/Users/saulrichardson/Library/CloudStorage/Dropbox/Remote Work Startups/main/data/processed"
global results        "/Users/saulrichardson/Library/CloudStorage/Dropbox/Remote Work Startups/main/results/raw"

// 1) Load core firm panel (var3/var5 instruments already present)
use "$processed_data/firm_panel.dta", clear

gen companyname_lower = lower(companyname)

// Construct half-year key for reliable merges
gen str7 yh_str = string(yh, "%th")
gen int yh_year = real(substr(yh_str, 1, 4))
gen byte yh_half = real(substr(yh_str, 6, 1))
gen long yh_key = yh_year*2 + (yh_half == 2)
assert !missing(yh_key)
drop yh_str yh_year yh_half

// 2) Merge location HHI metrics
di _n "Merging firm-level location HHI metrics"
preserve
    import delimited "$processed_data/firm_location_hhi.csv", clear varnames(1)
    rename yh_int yh_key
    tempfile loc_hhi
    save `loc_hhi'
restore

merge 1:1 companyname_lower yh_key using `loc_hhi', keep(match) nogen

 count if !missing(hhi)
local n_hhi = r(N)
 count if missing(hhi)
local n_missing = r(N)
di "  Non-missing HHI obs: `n_hhi'"
di "  Missing HHI obs:     `n_missing'"

label var hhi "Location HHI (0-1)"
label var hhi_10000 "Location HHI × 10,000"
label var effective_locations "Effective locations (1/HHI)"
label var n_cbsas "# CBSAs with headcount"
label var total_headcount "Total headcount in LinkedIn panel"

// 3) Prepare output
local specname "firm_scaling_location_hhi"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace

capture postclose handle_fs
tempfile out_fs
postfile handle_fs ///
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace

// 4) Run main regressions
// local outcome_vars ///
//       hhi hhi_10000 effective_locations n_cbsas ///
//       hhi_original hhi_original_10000 effective_locations_original n_cbsas_original
	  
	  
local outcome_vars ///
      hhi hhi_original
      

local fs_done = 0

foreach y of local outcome_vars {
    qui count if !missing(`y') & !missing(var3, var5, var4)
    if r(N) == 0 {
        di as text "Skipping `y' — no usable observations"
        continue
    }

    di as text "→ Processing outcome: `y'"
     summarize `y' if covid == 0
    local pre_mean = r(mean)

    // --- OLS ---
     reghdfe `y' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    // --- IV ---
     ivreghdfe `y' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    local rkf = e(rkf)
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`y'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }

    if !`fs_done' {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

         estimates restore _ivreg2_var3
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var3") ("`p'") (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
        }

         estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var5") ("`p'") (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
        }

        local fs_done = 1
    }
}

// 5) Export results
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

// log close
// exit
