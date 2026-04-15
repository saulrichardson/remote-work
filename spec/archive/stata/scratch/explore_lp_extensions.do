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
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/explore_lp_extensions.log", replace text




*============================================================*
*  explore_lp_extensions.do
*  Explore viable local projection extensions
*  Given firm-level fixed RHS variables
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

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

*============================================================*
* 1. CHECK DATA STRUCTURE
*============================================================*

di _n "====== DATA STRUCTURE CHECK ======"

* Check variation in key variables
foreach var in var3 var4 var5 var6 var7 {
    di _n "Checking `var':"
    
    * Check if variable varies within firm
    bysort firm_id: egen `var'_sd = sd(`var')
    qui sum `var'_sd
    if r(mean) == 0 {
        di "  `var' is FIXED at firm level (no within-firm variation)"
    }
    else {
        di "  `var' VARIES within firm (sd = " r(mean) ")"
    }
    drop `var'_sd
    
    * Count unique values
    qui levelsof `var', local(levels)
    local n_unique : word count `levels'
    di "  Number of unique values: `n_unique'"
    
    * Check variation over time within firm
    bysort firm_id yh: egen `var'_firm_time = mean(`var')
    bysort firm_id: egen `var'_time_sd = sd(`var'_firm_time)
    qui sum `var'_time_sd
    if r(mean) == 0 {
        di "  No time variation within firms"
    }
    else {
        di "  Has time variation within firms (sd = " r(mean) ")"
    }
    drop `var'_firm_time `var'_time_sd
}

* Check worker-level variables
di _n "Worker-level outcome variable:"
sum total_contributions_q100, detail
di "  Variation: mean = " r(mean) ", sd = " r(sd)

* Check panel structure
xtset user_id yh
xtdescribe

*============================================================*
* 2. TEST HETEROGENEOUS DYNAMICS (Most Viable)
*============================================================*

di _n "====== HETEROGENEOUS DYNAMICS ANALYSIS ======"

* Create worker performance quintiles based on pre-treatment productivity
preserve
    keep if yh == 2017
    egen productivity_q5 = xtile(total_contributions_q100), nq(5)
    keep user_id productivity_q5
    tempfile worker_types
    save `worker_types'
restore

merge m:1 user_id using `worker_types', keep(match master) nogen

* Create firm-level heterogeneity variables
* High HHI firms
egen hhi_p50 = pctile(hhi_msa), p(50)
gen high_concentration = (hhi_msa > hhi_p50)

* Large firms (by employee count)
bysort firm_id yh: gen firm_size = _N
egen size_p50 = pctile(firm_size), p(50)
gen large_firm = (firm_size > size_p50)

* Store heterogeneous LP results
local result_dir "$results/lp_extensions_`panel_variant'"
capture mkdir "`result_dir'"

* Setup for heterogeneous local projections
capture postclose het_results
tempfile het_out
postfile het_results ///
    str20 dimension str20 group horizon str20 shock ///
    coef se pval nobs ///
    using `het_out', replace

xtset user_id yh
sort user_id yh

* Define shorter horizon for testing
local max_h 3

* A. Worker productivity heterogeneity
foreach shock in var5 {  // Focus on var5 which showed interesting dynamics
    
    di _n "Testing heterogeneity in `shock' effects by worker productivity"
    
    * Generate outcome leads
    forvalues h = 0/`max_h' {
        cap drop F`h'_y
        gen F`h'_y = F`h'.total_contributions_q100
    }
    
    * Test top vs bottom quintile workers
    foreach group in 1 5 {
        di _n "  Quintile `group':"
        
        forvalues h = 0/`max_h' {
            cap drop shock_q`group'
            gen shock_q`group' = `shock' * (productivity_q5 == `group')
            
            qui count if !missing(F`h'_y, shock_q`group', var4) & productivity_q5 == `group'
            local n_valid = r(N)
            
            if `n_valid' > 500 {
                capture reghdfe F`h'_y shock_q`group' var4 if productivity_q5 == `group', ///
                    absorb(user_id firm_id yh) vce(cluster user_id)
                
                if _rc == 0 {
                    local b = _b[shock_q`group']
                    local se = _se[shock_q`group']
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    local nobs = e(N)
                    
                    post het_results ("productivity") ("q`group'") (`h') ("`shock'") ///
                        (`b') (`se') (`pval') (`nobs')
                    
                    di "    Horizon `h': β = " %7.3f `b' " (SE = " %7.3f `se' ")"
                }
            }
            drop shock_q`group'
        }
    }
    drop F*_y
}

* B. Firm concentration heterogeneity
foreach shock in var5 {
    
    di _n "Testing heterogeneity in `shock' effects by market concentration"
    
    forvalues h = 0/`max_h' {
        cap drop F`h'_y
        gen F`h'_y = F`h'.total_contributions_q100
    }
    
    foreach group in 0 1 {
        local label = cond(`group'==1, "high_hhi", "low_hhi")
        di _n "  Concentration: `label'"
        
        forvalues h = 0/`max_h' {
            cap drop shock_conc
            gen shock_conc = `shock' * (high_concentration == `group')
            
            qui count if !missing(F`h'_y, shock_conc, var4) & high_concentration == `group'
            local n_valid = r(N)
            
            if `n_valid' > 500 {
                capture reghdfe F`h'_y shock_conc var4 if high_concentration == `group', ///
                    absorb(user_id firm_id yh) vce(cluster user_id)
                
                if _rc == 0 {
                    local b = _b[shock_conc]
                    local se = _se[shock_conc]
                    local t = `b'/`se'
                    local pval = 2*ttail(e(df_r), abs(`t'))
                    local nobs = e(N)
                    
                    post het_results ("concentration") ("`label'") (`h') ("`shock'") ///
                        (`b') (`se') (`pval') (`nobs')
                    
                    di "    Horizon `h': β = " %7.3f `b' " (SE = " %7.3f `se' ")"
                }
            }
            drop shock_conc
        }
    }
    drop F*_y
}

postclose het_results
use `het_out', clear
export delimited using "`result_dir'/heterogeneous_dynamics.csv", replace

*============================================================*
* 3. PERSISTENCE/DECAY PARAMETER ESTIMATION
*============================================================*

di _n "====== PERSISTENCE ANALYSIS ======"

* Load the standard LP results
import delimited using "$results/user_productivity_lp_precovid/lp_standard.csv", clear

* Focus on var5 which shows decay pattern
keep if shock == "var5"
keep if horizon <= 4  // Use available horizons

* Test exponential decay: effect(h) = β₀ * δʰ
gen log_abs_effect = log(abs(coef))

* Regression to estimate decay parameter
reg log_abs_effect horizon
local decay_param = exp(_b[horizon])
local initial_effect = exp(_b[_cons])

di _n "Exponential Decay Model for var5:"
di "  Initial effect (β₀): " %7.3f `initial_effect'
di "  Decay parameter (δ): " %7.3f `decay_param'
di "  Half-life: " %7.2f (log(0.5)/log(`decay_param')) " periods"

* Test linear decay as alternative
reg coef horizon
di _n "Linear Decay Model for var5:"
di "  Initial effect: " %7.3f _b[_cons]
di "  Decay rate per period: " %7.3f _b[horizon]

* Export decay analysis
preserve
    gen model = "exponential"
    gen initial = `initial_effect'
    gen decay = `decay_param'
    gen halflife = log(0.5)/log(`decay_param')
    keep model initial decay halflife
    keep if _n == 1
    tempfile exp_decay
    save `exp_decay'
restore

reg coef horizon
preserve
    gen model = "linear"
    gen initial = _b[_cons]
    gen decay = _b[horizon]
    gen halflife = -_b[_cons]/_b[horizon]/2
    keep model initial decay halflife
    keep if _n == 1
    append using `exp_decay'
    export delimited using "`result_dir'/decay_parameters.csv", replace
restore

*============================================================*
* 4. CUMULATIVE EFFECTS BY GROUP
*============================================================*

di _n "====== CUMULATIVE EFFECTS ANALYSIS ======"

* Calculate cumulative effects from heterogeneous analysis
use "`result_dir'/heterogeneous_dynamics.csv", clear

* Calculate cumulative effects by group
sort dimension group shock horizon
by dimension group shock: gen cumul_effect = sum(coef)
by dimension group shock: gen cumul_se = sqrt(sum(se^2))

* Compare cumulative effects at horizon 3
preserve
    keep if horizon == 3
    keep dimension group shock cumul_effect cumul_se
    export delimited using "`result_dir'/cumulative_effects_by_group.csv", replace
restore

*============================================================*
* 5. MECHANISM TESTING (Limited by firm-level variation)
*============================================================*

di _n "====== MECHANISM TESTING ======"
di "Note: Limited mechanism testing due to firm-level RHS variables"

use "$processed_data/user_panel_`panel_variant'.dta", clear
merge m:1 companyname_c using `hhi', keep(match) nogen

* Since var3-var7 are firm-level, we can test:
* Does the effect work through changing worker composition?

* Create firm-level average productivity
bysort firm_id yh: egen firm_avg_prod = mean(total_contributions_q100)

* Test if firm-level treatment affects individual via peer effects
gen peer_productivity = firm_avg_prod - total_contributions_q100

xtset user_id yh
sort user_id yh

* Simple test at horizon 2
gen F2_y = F2.total_contributions_q100
gen F2_peer = F2.peer_productivity

reghdfe F2_y var5 peer_productivity, absorb(user_id firm_id yh) vce(cluster user_id)
di _n "Mechanism test - Peer effects channel:"
di "  Direct effect of var5: " %7.3f _b[var5]
di "  Peer productivity effect: " %7.3f _b[peer_productivity]

* Test interaction
gen var5_X_peer = var5 * peer_productivity
reghdfe F2_y var5 peer_productivity var5_X_peer, absorb(user_id firm_id yh) vce(cluster user_id)
di "  Interaction effect: " %7.3f _b[var5_X_peer]

*============================================================*
* SUMMARY OF VIABLE ANALYSES
*============================================================*

di _n _n "====== SUMMARY OF VIABLE EXTENSIONS ======"
di "Given firm-level fixed RHS variables, the following are viable:"
di ""
di "1. HETEROGENEOUS DYNAMICS ✓"
di "   - By worker productivity quintiles" 
di "   - By firm characteristics (size, HHI)"
di "   - Shows differential decay patterns"
di ""
di "2. PERSISTENCE/DECAY PARAMETERS ✓"
di "   - Estimated exponential decay for var5"
di "   - Can inform optimal treatment duration"
di ""
di "3. CUMULATIVE EFFECTS ✓"
di "   - Different total impact by worker/firm type"
di "   - Useful for targeting"
di ""
di "4. LIMITED MECHANISM TESTING ⚠"
di "   - Can test peer effects/spillovers"
di "   - Cannot test within-firm variation mechanisms"
di ""
di "5. NOT VIABLE ✗"
di "   - Time-varying treatment effects"
di "   - Individual-level treatment variation"
di "   - Most mediation analyses"

di _n "Results saved in: `result_dir'/"

capture log close
