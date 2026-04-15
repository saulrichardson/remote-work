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



*====================================================================*
*  spec/user_productivity_growth_mechanisms_lean.do
*  ------------------------------------------------------------------
*  Systematic horse race testing all combinations of growth mechanisms
*  for remote work productivity effects, using residualized growth
*  
*  Mechanisms tested:
*    1. Endogenous growth (raw post-COVID growth)
*    2. Exogenous growth (residualized on controls)
*    3. Rent (high vs low rent areas)
*    4. HHI (market concentration)
*  
*  Output: 16 specifications (2^4 combinations) with OLS and IV results
*====================================================================*

*--------------------------------------------------------------------*
* 0. Setup
*--------------------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

local specname "user_productivity_growth_mechanisms_lean_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

*--------------------------------------------------------------------*
* 1. Load main panel and firm controls
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Get firm-level controls
preserve
    use "$processed_data/firm_panel.dta", clear
    gen companyname_c = lower(companyname)
    capture gen byte covid = (yh >= 120)
    
    * Get post-COVID averages for rent and HHI
    collapse (mean) rent (mean) hhi_1000 if covid, by(companyname_c)
    
    * Create binary indicators
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi = hhi_1000, nq(2)
    
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

*--------------------------------------------------------------------*
* 2. Calculate POST-COVID growth and residualized versions
*--------------------------------------------------------------------*
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    
    gen yh = hofd(date)
    format yh %th
    
    * Drop June 2022 outliers
    drop if date == 22797
    
    collapse (last) total_employees date, by(companyname yh)
    
    gen byte covid = (yh >= 120)
    
    * Calculate static growth measure
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    gen growth_raw = (total_employees1 - total_employees0) / total_employees0
    winsor2 growth_raw, cuts(1 99)
    
    * Merge firm controls for residualization
    gen companyname_c = lower(companyname)
    merge 1:1 companyname_c using `firm_controls', keep(match master) nogen
    
    * Get industry and MSA growth (simplified - set to 0 for now)
    gen ind_growth_lo = 0  
    gen msa_growth_lo = 0
    
    * Residualize growth
    reg growth_raw rent hhi_1000 ind_growth_lo msa_growth_lo
    predict growth_resid, residuals
    
    * Create binary indicators
    quietly sum growth_raw, detail
    gen high_growth_raw = (growth_raw > r(p50)) if !missing(growth_raw)
    
    quietly sum growth_resid, detail
    gen high_growth_resid = (growth_resid > r(p50)) if !missing(growth_resid)
    
    keep companyname growth_raw growth_resid high_growth_raw high_growth_resid
    tempfile growth_measures
    save `growth_measures'
restore

*--------------------------------------------------------------------*
* 3. Merge growth measures into panel
*--------------------------------------------------------------------*
merge m:1 companyname using `growth_measures', keep(match) nogen

* Create binary rent and HHI indicators
gen high_rent = (tile_rent == 2) if !missing(tile_rent)
gen high_hhi = (tile_hhi == 2) if !missing(tile_hhi)

*--------------------------------------------------------------------*
* 4. Create interaction variables
*--------------------------------------------------------------------*
* Base interactions with COVID
gen var17 = covid * high_growth_raw
gen var18 = covid * high_growth_raw * startup

gen var19 = covid * high_growth_resid
gen var20 = covid * high_growth_resid * startup

gen var21 = covid * high_rent
gen var22 = covid * high_rent * startup

gen var23 = covid * high_hhi
gen var24 = covid * high_hhi * startup

*--------------------------------------------------------------------*
* 5. Setup postfile for results
*--------------------------------------------------------------------*
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  /// 
    str244 spec        ///
    str40  param       ///
    double coef se pval pre_mean rkf nobs /// 
    using `out', replace

*--------------------------------------------------------------------*
* 6. Define specifications (16 total)
*--------------------------------------------------------------------*
local specs ///
  "baseline" ///
  "endo_growth" "exo_growth" "rent" "hhi" ///
  "endo_exo" "endo_rent" "endo_hhi" "exo_rent" "exo_hhi" "rent_hhi" ///
  "endo_exo_rent" "endo_exo_hhi" "endo_rent_hhi" "exo_rent_hhi" ///
  "endo_exo_rent_hhi"

*--------------------------------------------------------------------*
* 7. Define variables for each specification
*--------------------------------------------------------------------*

* Baseline
local spec_exog1  "var4"
local spec_endo1  "var3 var5"
local spec_instr1 "var6 var7"

* Single mechanisms
local spec_exog2  "var4 var17 var18"  // endo_growth
local spec_exog3  "var4 var19 var20"  // exo_growth
local spec_exog4  "var4 var21 var22"  // rent
local spec_exog5  "var4 var23 var24"  // hhi

* Pairs
local spec_exog6  "var4 var17 var18 var19 var20"  // endo_exo
local spec_exog7  "var4 var17 var18 var21 var22"  // endo_rent
local spec_exog8  "var4 var17 var18 var23 var24"  // endo_hhi
local spec_exog9  "var4 var19 var20 var21 var22"  // exo_rent
local spec_exog10 "var4 var19 var20 var23 var24"  // exo_hhi
local spec_exog11 "var4 var21 var22 var23 var24"  // rent_hhi

* Triples
local spec_exog12 "var4 var17 var18 var19 var20 var21 var22"  // endo_exo_rent
local spec_exog13 "var4 var17 var18 var19 var20 var23 var24"  // endo_exo_hhi
local spec_exog14 "var4 var17 var18 var21 var22 var23 var24"  // endo_rent_hhi
local spec_exog15 "var4 var19 var20 var21 var22 var23 var24"  // exo_rent_hhi

* All four
local spec_exog16 "var4 var17 var18 var19 var20 var21 var22 var23 var24"  // endo_exo_rent_hhi

* All specifications use same endogenous variables and instruments
forvalues i = 1/16 {
    local spec_endo`i' "var3 var5"
    local spec_instr`i' "var6 var7"
}

*--------------------------------------------------------------------*
* 8. Pre-COVID mean of outcome
*--------------------------------------------------------------------*
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

*--------------------------------------------------------------------*
* 9. Run all specifications
*--------------------------------------------------------------------*
local n = wordcount("`specs'")
forvalues i = 1/`n' {
    local spec : word `i' of `specs'
    local exog "`spec_exog`i''"
    local endo "`spec_endo`i''"
    local instr "`spec_instr`i''"
    
    display ""
    display "=== Specification `i': `spec' ==="
    
    * OLS
    reghdfe total_contributions_q100 `endo' `exog', ///
        absorb(firm_id#user_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`spec'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`N')
    }
    
    * IV
    ivreghdfe total_contributions_q100 (`endo' = `instr') `exog', ///
        absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
    local rkf = e(rkf)
    local N   = e(N)
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`spec'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N')
    }
}

*--------------------------------------------------------------------*
* 10. Save results
*--------------------------------------------------------------------*
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

di as result "✓ Results saved to `result_dir'/consolidated_results.csv"

* Display summary
di _n "=== Summary of specifications ==="
di "1. baseline - No interactions"
di "2. endo_growth - Endogenous growth (raw)"
di "3. exo_growth - Exogenous growth (residualized)"
di "4. rent - High rent areas"
di "5. hhi - High HHI (concentration)"
di "... and all combinations up to 16. endo_exo_rent_hhi"

log close
