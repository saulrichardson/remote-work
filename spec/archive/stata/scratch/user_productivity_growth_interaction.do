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
log using "$LOG_DIR/user_productivity_growth_interaction.log", replace text




*====================================================================*
*  spec/user_productivity_growth_interaction.do
*  ------------------------------------------------------------------
*  Tests how post-COVID firm scaling affects the productivity impact
*  of remote work. Core idea: residualize firm growth to isolate 
*  firm-specific scaling from industry/location trends, then interact
*  with remote work treatment.
*
*  Specifications:
*    1. Static growth: (avg post-COVID / avg pre-COVID) - 1
*    2. Post-COVID average growth rate
*    3. Both continuous and dummy (above-median) interactions
*
*  Fixed effects: user_id, firm_id, industry#yh, msa#yh
*  Cluster: user_id
*====================================================================*

*--------------------------------------------------------------------*
* 0. Setup and arguments
*--------------------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* 1. Load main panel and prepare firm-level controls
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Get rent and HHI from firm panel
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    * Keep last observation per firm
    bysort companyname_c: keep if _n == _N
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

*--------------------------------------------------------------------*
* 2. Calculate firm growth measures from head count data
*--------------------------------------------------------------------*
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    
    * Date handling
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    
    gen yh = hofd(date)
    format yh %th
    
    * Drop June 2022 outliers
    drop if date == 22797
    
    * Collapse to firm-half-year level
    collapse (last) total_employees date, by(companyname yh)
    
    gen byte covid = (yh >= 120)
    
    *================================================================*
    * Growth Measure 1: Static pre-vs-post
    *================================================================*
    tempfile base_collapse
    save `base_collapse'
    
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    gen post_covid_growth = (total_employees1 - total_employees0) / total_employees0
    winsor2 post_covid_growth, cuts(1 99) suffix(_we)
    keep companyname post_covid_growth_we
    rename post_covid_growth_we growth_static
    tempfile growth_static
    save `growth_static'
    
    *================================================================*
    * Growth Measure 2: Average post-COVID growth rate
    *================================================================*
    use `base_collapse', clear
    keep if covid == 1  // Post-COVID only
    
    encode companyname, gen(firm_n)
    xtset firm_n yh
    
    gen growth_rate = (total_employees / L.total_employees) - 1
    winsor2 growth_rate, cuts(1 99) suffix(_we)
    
    collapse (mean) growth_rate_we, by(companyname)
    rename growth_rate_we growth_avg_post
    tempfile growth_avg
    save `growth_avg'
restore

*--------------------------------------------------------------------*
* 3. Merge growth measures back to main panel
*--------------------------------------------------------------------*
merge m:1 companyname using `growth_static', keep(match) nogen
merge m:1 companyname using `growth_avg', keep(match) nogen

*--------------------------------------------------------------------*
* 4. Get industry and MSA averages for residualization
*--------------------------------------------------------------------*
* For each firm, calculate leave-one-out industry/MSA growth means
preserve
    keep companyname industry company_msa growth_static growth_avg_post
    duplicates drop
    
    * Industry leave-one-out means
    bysort industry: egen ind_sum_static = sum(growth_static)
    bysort industry: egen ind_n = count(growth_static)
    gen ind_growth_static_lo = (ind_sum_static - growth_static) / (ind_n - 1) if ind_n > 1
    
    bysort industry: egen ind_sum_avg = sum(growth_avg_post)
    gen ind_growth_avg_lo = (ind_sum_avg - growth_avg_post) / (ind_n - 1) if ind_n > 1
    
    * MSA leave-one-out means
    bysort company_msa: egen msa_sum_static = sum(growth_static)
    bysort company_msa: egen msa_n = count(growth_static)
    gen msa_growth_static_lo = (msa_sum_static - growth_static) / (msa_n - 1) if msa_n > 1
    
    bysort company_msa: egen msa_sum_avg = sum(growth_avg_post)
    gen msa_growth_avg_lo = (msa_sum_avg - growth_avg_post) / (msa_n - 1) if msa_n > 1
    
    keep companyname ind_growth_static_lo ind_growth_avg_lo msa_growth_static_lo msa_growth_avg_lo
    * Collapse to ensure unique companies
    collapse (first) ind_growth_static_lo ind_growth_avg_lo msa_growth_static_lo msa_growth_avg_lo, by(companyname)
    tempfile growth_controls
    save `growth_controls'
restore

merge m:1 companyname using `growth_controls', keep(match) nogen

*--------------------------------------------------------------------*
* 5. Setup output files and logging
*--------------------------------------------------------------------*

local result_dir "$results/growth_interaction_`panel_variant'"
cap mkdir "`result_dir'"

tempfile results_out
capture postclose results
postfile results ///
    str32 growth_type str10 spec_type ///
    double b3 se3 p3 /// base remote effect
    double b5 se5 p5 /// startup-remote effect  
    double b3g se3g p3g /// growth interaction
    double b5g se5g p5g /// startup-growth interaction
    double rkf nobs ///
    using `results_out', replace

*--------------------------------------------------------------------*
* 6. Run regressions for each growth measure
*--------------------------------------------------------------------*
foreach gvar in "growth_static" "growth_avg_post" {
    
    di _n "==== Testing growth measure: `gvar' ===="
    
    * Residualize growth on controls
    if "`gvar'" == "growth_static" {
        local ind_var "ind_growth_static_lo"
        local msa_var "msa_growth_static_lo"
    }
    else {
        local ind_var "ind_growth_avg_lo" 
        local msa_var "msa_growth_avg_lo"
    }
    
    quietly reg `gvar' rent hhi_1000 `ind_var' `msa_var'
    quietly predict g_resid, residuals
    quietly sum g_resid
    gen g_c = g_resid - r(mean)
    
    *----------------------------------------------------------------*
    * A. Continuous interaction specification
    *----------------------------------------------------------------*
    * Create interaction terms
    foreach v in var3 var5 var6 var7 {
        gen `v'_g = `v' * g_c
    }
    
    * Run IV regression
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_g var5_g = var6 var7 var6_g var7_g) ///
        var4 c.g_c ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    * Store results
    local b3 = _b[var3]
    local se3 = _se[var3]
    local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
    
    local b5 = _b[var5]
    local se5 = _se[var5]
    local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
    
    local b3g = _b[var3_g]
    local se3g = _se[var3_g]
    local p3g = 2*ttail(e(df_r), abs(`b3g'/`se3g'))
    
    local b5g = _b[var5_g]
    local se5g = _se[var5_g]
    local p5g = 2*ttail(e(df_r), abs(`b5g'/`se5g'))
    
    post results ("`gvar'") ("continuous") ///
        (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') ///
        (`b3g') (`se3g') (`p3g') ///
        (`b5g') (`se5g') (`p5g') ///
        (e(rkf)) (e(N))
    
    * Clean up continuous interaction terms
    drop var3_g var5_g var6_g var7_g
    
    *----------------------------------------------------------------*
    * B. Dummy interaction specification (above median)
    *----------------------------------------------------------------*
    quietly sum g_resid, detail
    gen hi_growth = (g_resid > r(p50)) if !missing(g_resid)
    
    * Create dummy interactions
    foreach v in var3 var5 var6 var7 {
        gen `v'_hi = `v' * hi_growth
    }
    
    * Run IV regression with dummy
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_hi var5_hi = var6 var7 var6_hi var7_hi) ///
        var4 hi_growth ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    * Store results
    local b3 = _b[var3]
    local se3 = _se[var3]
    local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
    
    local b5 = _b[var5]
    local se5 = _se[var5]
    local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
    
    local b3g = _b[var3_hi]
    local se3g = _se[var3_hi]
    local p3g = 2*ttail(e(df_r), abs(`b3g'/`se3g'))
    
    local b5g = _b[var5_hi]
    local se5g = _se[var5_hi]
    local p5g = 2*ttail(e(df_r), abs(`b5g'/`se5g'))
    
    post results ("`gvar'") ("dummy") ///
        (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') ///
        (`b3g') (`se3g') (`p3g') ///
        (`b5g') (`se5g') (`p5g') ///
        (e(rkf)) (e(N))
    
    * Clean up
    drop var3_hi var5_hi var6_hi var7_hi hi_growth g_resid g_c
}

*--------------------------------------------------------------------*
* 7. Save results
*--------------------------------------------------------------------*
postclose results
use `results_out', clear
export delimited using "`result_dir'/results.csv", replace

di _n as result "✓ Results saved to `result_dir'/results.csv"

log close
