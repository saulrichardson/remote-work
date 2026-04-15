// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



*============================================================*
*  user_productivity_local_projections.do
*  Local Projection Methods for Dynamic Treatment Effects
*  Analyzes productivity (percentile rank) responses to var3, var4, var5
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_lp_`panel_variant'
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

* Merge HHI data
drop if _merge == .
drop _merge
gen companyname_c = lower(companyname)
preserve
    import delimited "$processed_data/firm_hhi_msa.csv", clear
    rename companyname companyname_c
    tempfile hhi
    save `hhi'
restore
merge m:1 companyname_c using `hhi', keep(match) nogen

* Setup output directory
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

*============================================================*
* 1. STANDARD LOCAL PROJECTIONS (Jordà 2005)
*============================================================*

* Store results for plotting
capture postclose lp_results
tempfile lp_out
postfile lp_results ///
    horizon str20 shock str20 outcome ///
    coef se ci_low ci_high pval nobs ///
    using `lp_out', replace

* Define horizons (0 = impact, 1-8 = future periods)
local max_horizon 4  // Reduced to avoid data issues at longer horizons

* Sort panel for lead generation
xtset user_id yh
sort user_id yh

foreach outcome in total_contributions_q100 {
    
    * Generate leads of outcome variable
    forvalues h = 0/`max_horizon' {
        cap drop F`h'_`outcome'
        gen F`h'_`outcome' = F`h'.`outcome'
    }
    
    * Loop over each shock variable - matching original specification
    foreach shock in var3 var5 {
        
        di _n "==== Local Projections: `shock' → `outcome' ===="
        
        forvalues h = 0/`max_horizon' {
            
            * Count non-missing observations for this horizon
            qui count if !missing(F`h'_`outcome', `shock', var4)
            local n_valid = r(N)
            
            if `n_valid' > 1000 {  // Only run if sufficient observations
                
                * Standard LP regression - single shock at a time like original
                capture reghdfe F`h'_`outcome' `shock' var4, ///
                    absorb(user_id firm_id yh) vce(cluster user_id)
                
                if _rc == 0 {
                    * Store results
                    local b = _b[`shock']
                    local se = _se[`shock']
                    local ci_low = `b' - 1.96*`se'
                    local ci_high = `b' + 1.96*`se'
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    local nobs = e(N)
                    
                    post lp_results (`h') ("`shock'") ("`outcome'") ///
                        (`b') (`se') (`ci_low') (`ci_high') (`pval') (`nobs')
                    
                    di "Horizon `h': β = " %9.4f `b' " (SE = " %9.4f `se' ") N = " `nobs'
                }
                else {
                    di "Horizon `h': Regression failed"
                }
            }
            else {
                di "Horizon `h': Insufficient observations (N = `n_valid')"
            }
        }
    }
    
    * Clean up lead variables
    drop F*_`outcome'
}

* Save LP results
postclose lp_results
use `lp_out', clear
export delimited using "`result_dir'/lp_standard.csv", replace

*============================================================*
* 2. IV LOCAL PROJECTIONS - Matching Original Specification
*============================================================*

use "$processed_data/user_panel_`panel_variant'.dta", clear
drop if _merge == .
drop _merge
gen companyname_c = lower(companyname)
merge m:1 companyname_c using `hhi', keep(match) nogen
xtset user_id yh
sort user_id yh

capture postclose lp_iv_results
tempfile lp_iv_out
postfile lp_iv_results ///
    horizon str20 shock str20 outcome ///
    coef se ci_low ci_high pval rkf nobs ///
    using `lp_iv_out', replace

foreach outcome in total_contributions_q100 {
    
    * Generate leads
    forvalues h = 0/`max_horizon' {
        cap drop F`h'_`outcome'
        gen F`h'_`outcome' = F`h'.`outcome'
    }
    
    di _n "==== IV Local Projections: var3, var5 → `outcome' ===="
    
    forvalues h = 0/`max_horizon' {
        
        * Count valid observations
        qui count if !missing(F`h'_`outcome', var3, var5, var4, var6, var7)
        local n_valid = r(N)
        
        if `n_valid' > 1000 {
            
            * IV LP regression - matching original with both endogenous vars
            capture ivreghdfe F`h'_`outcome' (var3 var5 = var6 var7) var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            
            if _rc == 0 {
                local rkf = e(rkf)
                local nobs = e(N)
                
                * Store results for each endogenous variable
                foreach shock in var3 var5 {
                    local b = _b[`shock']
                    local se = _se[`shock']
                    local ci_low = `b' - 1.96*`se'
                    local ci_high = `b' + 1.96*`se'
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    
                    post lp_iv_results (`h') ("`shock'") ("`outcome'") ///
                        (`b') (`se') (`ci_low') (`ci_high') (`pval') (`rkf') (`nobs')
                    
                    di "Horizon `h' (`shock'): β = " %9.4f `b' " (SE = " %9.4f `se' ") rkf = " %6.2f `rkf'
                }
            }
            else {
                di "Horizon `h': IV regression failed"
            }
        }
        else {
            di "Horizon `h': Insufficient observations (N = `n_valid')"
        }
    }
    
    drop F*_`outcome'
}

postclose lp_iv_results
use `lp_iv_out', clear
export delimited using "`result_dir'/lp_iv.csv", replace

*============================================================*
* 3. COMBINED OLS LOCAL PROJECTIONS (Both shocks together)
*============================================================*

use "$processed_data/user_panel_`panel_variant'.dta", clear
drop if _merge == .
drop _merge
gen companyname_c = lower(companyname)
merge m:1 companyname_c using `hhi', keep(match) nogen
xtset user_id yh
sort user_id yh

capture postclose lp_combined_results
tempfile lp_combined_out
postfile lp_combined_results ///
    horizon str20 shock str20 outcome ///
    coef se ci_low ci_high pval nobs ///
    using `lp_combined_out', replace

foreach outcome in total_contributions_q100 {
    
    * Generate leads
    forvalues h = 0/`max_horizon' {
        cap drop F`h'_`outcome'
        gen F`h'_`outcome' = F`h'.`outcome'
    }
    
    di _n "==== Combined OLS Local Projections: var3 + var5 → `outcome' ===="
    
    forvalues h = 0/`max_horizon' {
        
        * Count valid observations
        qui count if !missing(F`h'_`outcome', var3, var5, var4)
        local n_valid = r(N)
        
        if `n_valid' > 1000 {
            
            * Combined OLS regression - matching original but with both shocks
            capture reghdfe F`h'_`outcome' var3 var5 var4, ///
                absorb(user_id firm_id yh) vce(cluster user_id)
            
            if _rc == 0 {
                local nobs = e(N)
                
                * Store results for each shock
                foreach shock in var3 var5 {
                    local b = _b[`shock']
                    local se = _se[`shock']
                    local ci_low = `b' - 1.96*`se'
                    local ci_high = `b' + 1.96*`se'
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    
                    post lp_combined_results (`h') ("`shock'") ("`outcome'") ///
                        (`b') (`se') (`ci_low') (`ci_high') (`pval') (`nobs')
                    
                    di "Horizon `h' (`shock'): β = " %9.4f `b' " (SE = " %9.4f `se' ")"
                }
            }
            else {
                di "Horizon `h': Regression failed"
            }
        }
        else {
            di "Horizon `h': Insufficient observations (N = `n_valid')"
        }
    }
    
    drop F*_`outcome'
}

postclose lp_combined_results
use `lp_combined_out', clear
export delimited using "`result_dir'/lp_combined.csv", replace

*============================================================*
* 4. VISUALIZATION CODE
*============================================================*

* Create simple comparison plots
capture {
    use "`result_dir'/lp_standard.csv", clear
    
    * Plot for var3 effect
    twoway (connected coef horizon if shock=="var3", lcolor(navy) mcolor(navy)) ///
           (rcap ci_low ci_high horizon if shock=="var3", lcolor(navy)), ///
           yline(0, lcolor(gray) lpattern(dash)) ///
           xlabel(0(1)`max_horizon') ///
           xtitle("Horizon (periods)") ///
           ytitle("Effect on Productivity Percentile") ///
           title("Local Projection: var3 → Productivity") ///
           legend(off)
    graph export "`result_dir'/lp_var3.png", replace
    
    * Plot for var5 effect
    twoway (connected coef horizon if shock=="var5", lcolor(maroon) mcolor(maroon)) ///
           (rcap ci_low ci_high horizon if shock=="var5", lcolor(maroon)), ///
           yline(0, lcolor(gray) lpattern(dash)) ///
           xlabel(0(1)`max_horizon') ///
           xtitle("Horizon (periods)") ///
           ytitle("Effect on Productivity Percentile") ///
           title("Local Projection: var5 → Productivity") ///
           legend(off)
    graph export "`result_dir'/lp_var5.png", replace
}

di as result "======================================"
di as result "Local Projection Results Saved:"
di as result "  Standard LP: `result_dir'/lp_standard.csv"
di as result "  IV LP: `result_dir'/lp_iv.csv"
di as result "  Smooth LP: `result_dir'/lp_smooth.csv"
di as result "  Cumulative: `result_dir'/lp_cumulative.csv"
di as result "  State-Dependent: `result_dir'/lp_state_dependent.csv"
di as result "======================================"

capture log close
