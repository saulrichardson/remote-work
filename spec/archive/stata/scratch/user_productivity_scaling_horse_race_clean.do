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
log using "$LOG_DIR/scaling_horse_race_clean.log", replace text




*====================================================================*
*  spec/user_productivity_scaling_horse_race_clean.do
*  ------------------------------------------------------------------
*  Clean horse race specification with simple interaction approach
*  Panel A: OLS estimates
*  Panel B: IV estimates
*
*  Main effects show average effects across all firms
*  Interactions show differential effects for high X firms
*====================================================================*

*--------------------------------------------------------------------*
* 0. Setup
*--------------------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* 1. Load main panel with all needed variables
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

* Get firm-level controls
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    bysort companyname_c: keep if _n == _N
    tempfile firm_controls
    save `firm_controls'
restore

merge m:1 companyname_c using `firm_controls', keep(match) nogen

*--------------------------------------------------------------------*
* 2. Calculate POST-COVID growth
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
    
    * Static growth measure
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    gen post_covid_growth = (total_employees1 - total_employees0) / total_employees0
    winsor2 post_covid_growth, cuts(1 99) suffix(_we)
    keep companyname post_covid_growth_we
    rename post_covid_growth_we growth_post
    tempfile post_growth
    save `post_growth'
restore

*--------------------------------------------------------------------*
* 3. Get vacancy data
*--------------------------------------------------------------------*
preserve
    import delimited "$processed_data/vacancy_measures_2020.csv", clear
    keep companyname vacancy_per_size
    destring vacancy_per_size, replace force
    rename vacancy_per_size vacancy_rate
    tempfile vacancy
    save `vacancy'
restore

*--------------------------------------------------------------------*
* 4. Merge all firm-level data
*--------------------------------------------------------------------*
merge m:1 companyname using `post_growth', keep(match) nogen
merge m:1 companyname using `vacancy', keep(match master) nogen

*--------------------------------------------------------------------*
* 5. Create residualized growth measure
*--------------------------------------------------------------------*
* For now using only rent and HHI (no leave-one-out industry/MSA)
reg growth_post rent hhi_1000
predict growth_resid, residuals

*--------------------------------------------------------------------*
* 6. Create binary indicators (above median = 1)
*--------------------------------------------------------------------*
* Growth measures
quietly sum growth_post, detail
gen high_growth = (growth_post > r(p50)) if !missing(growth_post)

quietly sum growth_resid, detail
gen high_growth_resid = (growth_resid > r(p50)) if !missing(growth_resid)

* Rent
quietly sum rent, detail
gen high_rent = (rent > r(p50)) if !missing(rent)

* HHI
quietly sum hhi_1000, detail
gen high_hhi = (hhi_1000 > r(p50)) if !missing(hhi_1000)

*--------------------------------------------------------------------*
* 7. Create clean interaction variables
*--------------------------------------------------------------------*
* These show DIFFERENTIAL effects for high X firms
gen var3_highgrowth = var3 * high_growth
gen var5_highgrowth = var5 * high_growth

gen var3_highgrowth_resid = var3 * high_growth_resid
gen var5_highgrowth_resid = var5 * high_growth_resid

gen var3_highrent = var3 * high_rent
gen var5_highrent = var5 * high_rent

gen var3_highhhi = var3 * high_hhi
gen var5_highhhi = var5 * high_hhi

* Also create instrument interactions
gen var6_highgrowth = var6 * high_growth
gen var7_highgrowth = var7 * high_growth

gen var6_highgrowth_resid = var6 * high_growth_resid
gen var7_highgrowth_resid = var7 * high_growth_resid

gen var6_highrent = var6 * high_rent
gen var7_highrent = var7 * high_rent

gen var6_highhhi = var6 * high_hhi
gen var7_highhhi = var7 * high_hhi

*--------------------------------------------------------------------*
* 8. Setup results tracking
*--------------------------------------------------------------------*
local result_dir "$results/scaling_horse_race_clean_`panel_variant'"
cap mkdir "`result_dir'"

tempfile results_out
capture postclose results
postfile results ///
    str32 specification ///
    str10 method ///
    double b3 se3 p3 /// main remote effect
    double b5 se5 p5 /// main startup effect  
    double b3_int se3_int p3_int /// differential effect
    double b5_int se5_int p5_int /// differential startup effect
    double fstat nobs ///
    using `results_out', replace

*--------------------------------------------------------------------*
* 9. Run specifications
*--------------------------------------------------------------------*
foreach spec in "baseline" "growth" "growth_resid" "rent" "hhi" {
    
    di _n "==== Specification: `spec' ===="
    
    * Set up variables for this specification
    if "`spec'" == "baseline" {
        local controls "var4"
        local interactions ""
        local iv_endo "var3 var5"
        local iv_inst "var6 var7"
        local high_var ""
    }
    else if "`spec'" == "growth" {
        local controls "var4 high_growth"
        local interactions "var3_highgrowth var5_highgrowth"
        local iv_endo "var3 var5 var3_highgrowth var5_highgrowth"
        local iv_inst "var6 var7 var6_highgrowth var7_highgrowth"
        local high_var "high_growth"
    }
    else if "`spec'" == "growth_resid" {
        local controls "var4 high_growth_resid"
        local interactions "var3_highgrowth_resid var5_highgrowth_resid"
        local iv_endo "var3 var5 var3_highgrowth_resid var5_highgrowth_resid"
        local iv_inst "var6 var7 var6_highgrowth_resid var7_highgrowth_resid"
        local high_var "high_growth_resid"
    }
    else if "`spec'" == "rent" {
        local controls "var4 high_rent"
        local interactions "var3_highrent var5_highrent"
        local iv_endo "var3 var5 var3_highrent var5_highrent"
        local iv_inst "var6 var7 var6_highrent var7_highrent"
        local high_var "high_rent"
    }
    else if "`spec'" == "hhi" {
        local controls "var4 high_hhi"
        local interactions "var3_highhhi var5_highhhi"
        local iv_endo "var3 var5 var3_highhhi var5_highhhi"
        local iv_inst "var6 var7 var6_highhhi var7_highhhi"
        local high_var "high_hhi"
    }
    
    * Run OLS
    di "--- OLS ---"
    reghdfe total_contributions_q100 var3 var5 `interactions' `controls', ///
        absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    * Store OLS results
    local b3_ols = _b[var3]
    local se3_ols = _se[var3]
    local p3_ols = 2*ttail(e(df_r), abs(`b3_ols'/`se3_ols'))
    local b5_ols = _b[var5]
    local se5_ols = _se[var5]
    local p5_ols = 2*ttail(e(df_r), abs(`b5_ols'/`se5_ols'))
    
    if "`spec'" != "baseline" {
        local int1 : word 1 of `interactions'
        local int2 : word 2 of `interactions'
        local b3_int_ols = _b[`int1']
        local se3_int_ols = _se[`int1']
        local p3_int_ols = 2*ttail(e(df_r), abs(`b3_int_ols'/`se3_int_ols'))
        local b5_int_ols = _b[`int2']
        local se5_int_ols = _se[`int2']
        local p5_int_ols = 2*ttail(e(df_r), abs(`b5_int_ols'/`se5_int_ols'))
    }
    else {
        local b3_int_ols = .
        local se3_int_ols = .
        local p3_int_ols = .
        local b5_int_ols = .
        local se5_int_ols = .
        local p5_int_ols = .
    }
    local fstat_ols = e(F)
    local nobs_ols = e(N)
    
    post results ("`spec'") ("OLS") (`b3_ols') (`se3_ols') (`p3_ols') ///
        (`b5_ols') (`se5_ols') (`p5_ols') (`b3_int_ols') (`se3_int_ols') (`p3_int_ols') ///
        (`b5_int_ols') (`se5_int_ols') (`p5_int_ols') (`fstat_ols') (`nobs_ols')
    
    * Run IV
    di "--- IV ---"
    ivreghdfe total_contributions_q100 ///
        (`iv_endo' = `iv_inst') ///
        `controls' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    * Store IV results
    local b3_iv = _b[var3]
    local se3_iv = _se[var3]
    local p3_iv = 2*ttail(e(df_r), abs(`b3_iv'/`se3_iv'))
    local b5_iv = _b[var5]
    local se5_iv = _se[var5]
    local p5_iv = 2*ttail(e(df_r), abs(`b5_iv'/`se5_iv'))
    
    if "`spec'" != "baseline" {
        local int1 : word 1 of `interactions'
        local int2 : word 2 of `interactions'
        local b3_int_iv = _b[`int1']
        local se3_int_iv = _se[`int1']
        local p3_int_iv = 2*ttail(e(df_r), abs(`b3_int_iv'/`se3_int_iv'))
        local b5_int_iv = _b[`int2']
        local se5_int_iv = _se[`int2']
        local p5_int_iv = 2*ttail(e(df_r), abs(`b5_int_iv'/`se5_int_iv'))
    }
    else {
        local b3_int_iv = .
        local se3_int_iv = .
        local p3_int_iv = .
        local b5_int_iv = .
        local se5_int_iv = .
        local p5_int_iv = .
    }
    local fstat_iv = e(rkf)
    local nobs_iv = e(N)
    
    post results ("`spec'") ("IV") (`b3_iv') (`se3_iv') (`p3_iv') ///
        (`b5_iv') (`se5_iv') (`p5_iv') (`b3_int_iv') (`se3_int_iv') (`p3_int_iv') ///
        (`b5_int_iv') (`se5_int_iv') (`p5_int_iv') (`fstat_iv') (`nobs_iv')
}

*--------------------------------------------------------------------*
* 10. Save and display results
*--------------------------------------------------------------------*
postclose results
use `results_out', clear

* Export results
export delimited using "`result_dir'/horse_race_clean_results.csv", replace

* Create summary display
di _n "=== SUMMARY OF RESULTS ==="
list specification method b3 b3_int b5 b5_int if method == "IV"

* Save for LaTeX
save "`result_dir'/horse_race_clean_results.dta", replace

di _n as result "✓ Results saved to `result_dir'/horse_race_clean_results.csv"

log close
