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

*=============================================================================*
* Test scaling with composition changes controlling for industry/location
* Residualizes growth to isolate firm-specific effects from trends
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Load firm panel with composition
*-----------------------------------------------------------------------------*

use "$processed_data/firm_panel.dta", clear
gen companyname_lower = lower(companyname)

* Keep COVID period
keep if covid == 1

* Merge composition data
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen

* Get industry and MSA info
preserve
    use "$processed_data/user_panel_precovid.dta", clear
    keep companyname industry company_msa
    gen companyname_lower = lower(companyname)
    bysort companyname_lower: keep if _n == 1
    tempfile ind_msa
    save `ind_msa'
restore

merge m:1 companyname_lower using `ind_msa', keep(match) nogen

*-----------------------------------------------------------------------------*
* Part 2: Calculate leave-one-out industry/MSA growth means
*-----------------------------------------------------------------------------*

* Create firm-period identifier
egen firm_period = group(firm_id yh)

* Industry leave-one-out means
bysort industry yh: egen ind_growth_sum = sum(growth_rate_we)
bysort industry yh: egen ind_n = count(growth_rate_we)
gen ind_growth_lo = (ind_growth_sum - growth_rate_we) / (ind_n - 1) if ind_n > 1

* MSA leave-one-out means
bysort company_msa yh: egen msa_growth_sum = sum(growth_rate_we)
bysort company_msa yh: egen msa_n = count(growth_rate_we)
gen msa_growth_lo = (msa_growth_sum - growth_rate_we) / (msa_n - 1) if msa_n > 1

* Industry × time fixed effects approach
bysort industry yh: egen ind_yh_mean = mean(growth_rate_we)

*-----------------------------------------------------------------------------*
* Part 3: Residualize growth
*-----------------------------------------------------------------------------*

* Method 1: Control for leave-one-out means
reg growth_rate_we ind_growth_lo msa_growth_lo rent hhi_1000 age i.yh, robust
predict growth_resid1, residuals

* Method 2: Industry × time FE
areg growth_rate_we rent hhi_1000 age i.yh, absorb(industry) robust
predict growth_resid2, residuals

* Standardize residuals
sum growth_resid1
gen growth_resid1_std = growth_resid1 / r(sd)

sum growth_resid2  
gen growth_resid2_std = growth_resid2 / r(sd)

*-----------------------------------------------------------------------------*
* Part 4: Test composition effects on residualized growth
*-----------------------------------------------------------------------------*

di _n "=== COMPOSITION EFFECTS ON RESIDUALIZED GROWTH ==="

* Get list of SOC variables
ds pct_chg_soc*
local soc_vars `r(varlist)'

* Store results
capture postclose resid_results
tempfile resid_out
postfile resid_results str20 method str20 soc ///
    double b_startup se_startup p_startup ///
    double b_comp se_comp p_comp ///
    double b_int se_int p_int ///
    double r2 long nobs ///
    using `resid_out', replace

* Test each residualization method
foreach method in "resid1" "resid2" {
    
    di _n "Method: " "`method'"
    
    * Full model with all SOCs
    if "`method'" == "resid1" {
        local depvar "growth_resid1_std"
        local controls "ind_growth_lo msa_growth_lo"
    }
    else {
        local depvar "growth_resid2_std"
        local controls "i.industry"
    }
    
    reg `depvar' startup age rent hhi_1000 `soc_vars' i.yh, robust
    
    di _n "Joint test of composition variables:"
    testparm `soc_vars'
    
    * Individual SOC interactions
    foreach var of local soc_vars {
        local soc = substr("`var'", 12, .)
        
        quietly reg `depvar' startup age rent hhi_1000 ///
            `var' c.startup#c.`var' ///
            i.yh, robust
        
        local b_startup = _b[startup]
        local se_startup = _se[startup]
        local p_startup = 2*ttail(e(df_r), abs(`b_startup'/`se_startup'))
        
        local b_comp = _b[`var']
        local se_comp = _se[`var']
        local p_comp = 2*ttail(e(df_r), abs(`b_comp'/`se_comp'))
        
        local b_int = _b[c.startup#c.`var']
        local se_int = _se[c.startup#c.`var']
        local p_int = 2*ttail(e(df_r), abs(`b_int'/`se_int'))
        
        post resid_results ("`method'") ("`soc'") ///
            (`b_startup') (`se_startup') (`p_startup') ///
            (`b_comp') (`se_comp') (`p_comp') ///
            (`b_int') (`se_int') (`p_int') ///
            (e(r2)) (e(N))
    }
}

postclose resid_results

*-----------------------------------------------------------------------------*
* Part 5: Compare to baseline (no residualization)
*-----------------------------------------------------------------------------*

di _n "=== BASELINE (NO RESIDUALIZATION) ==="

* Top 3 SOCs with interactions
local top3_socs "pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191"

foreach var of local top3_socs {
    gen startup_X_`var' = startup * `var'
}

reg growth_rate_we startup age rent hhi_1000 ///
    `top3_socs' ///
    startup_X_* ///
    i.yh, robust

testparm startup_X_*
local f_base = r(F)
local p_base = r(p)

*-----------------------------------------------------------------------------*
* Part 6: Display comparison
*-----------------------------------------------------------------------------*

di _n "=== COMPARISON OF RESULTS ==="

use `resid_out', clear

* Show significant interactions
di _n "Significant startup × composition interactions (p < 0.10):"
list method soc b_int p_int if p_int < 0.10

* Compare R-squared
di _n "Model fit by method:"
collapse (mean) r2, by(method)
list

* Summary
di _n "Baseline F-test for interactions: F = " %8.2f `f_base' ", p = " %8.4f `p_base'

di _n "Analysis complete!"