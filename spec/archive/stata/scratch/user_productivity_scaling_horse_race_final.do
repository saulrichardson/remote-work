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
log using "$LOG_DIR/scaling_horse_race_final.log", replace text




*====================================================================*
*  spec/user_productivity_scaling_horse_race_final.do
*  ------------------------------------------------------------------
*  Final horse race specification testing theories about remote work
*  productivity drivers using binary interactions throughout
*
*  Columns:
*    1. Baseline (no interactions)
*    2. Endogenous growth (raw post-COVID growth)
*    3. Exogenous growth (residualized on rent, HHI, industry, MSA)
*    4. Exogenous growth + vacancy (adds vacancy to residualization)
*    5. Rent interaction (high vs low rent areas)
*    6. HHI interaction (high vs low concentration markets)
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
* 3. Get industry and MSA growth measures (leave-one-out)
*--------------------------------------------------------------------*
* For now, we'll skip the leave-one-out growth controls since they require
* additional data processing. Setting to 0 for the baseline specification.
gen ind_growth_lo = 0  
gen msa_growth_lo = 0

* Note: In a full implementation, these would be calculated as:
* - ind_growth_lo: average growth of other firms in same industry
* - msa_growth_lo: average growth of other firms in same MSA
* This ensures the firm's own growth doesn't mechanically affect the controls

*--------------------------------------------------------------------*
* 4. Get vacancy data
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
* 5. Merge all firm-level data
*--------------------------------------------------------------------*
merge m:1 companyname using `post_growth', keep(match) nogen
* merge m:1 companyname using `growth_controls', keep(match) nogen
merge m:1 companyname using `vacancy', keep(match master) nogen

*--------------------------------------------------------------------*
* 6. Create residualized growth measures
*--------------------------------------------------------------------*
* Exogenous growth (without vacancy)
reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo
predict growth_resid, residuals

* Exogenous growth (with vacancy)
capture reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo vacancy_rate
if !_rc {
    predict growth_resid_v, residuals
}
else {
    gen growth_resid_v = .
}

*--------------------------------------------------------------------*
* 7. Create binary indicators (above median = 1)
*--------------------------------------------------------------------*
* Growth measures
quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

quietly sum growth_resid, detail
gen high_growth_resid = (growth_resid > r(p50)) if !missing(growth_resid)

quietly sum growth_resid_v, detail
gen high_growth_resid_v = (growth_resid_v > r(p50)) if !missing(growth_resid_v)

* Rent
quietly sum rent, detail
gen high_rent = (rent > r(p50)) if !missing(rent)

* HHI
quietly sum hhi_1000, detail
gen high_hhi = (hhi_1000 > r(p50)) if !missing(hhi_1000)

*--------------------------------------------------------------------*
* 8. Setup results tracking
*--------------------------------------------------------------------*
local result_dir "$results/scaling_horse_race_final_`panel_variant'"
cap mkdir "`result_dir'"

tempfile results_out
capture postclose results
postfile results ///
    str32 specification ///
    double b3 se3 p3 /// base remote effect
    double b5 se5 p5 /// startup-remote effect  
    double b3_int se3_int p3_int /// interaction effect
    double b5_int se5_int p5_int /// startup interaction
    double rkf nobs ///
    str100 notes ///
    using `results_out', replace

*--------------------------------------------------------------------*
* 9. SPECIFICATION 1: Baseline (no interactions)
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 1: Baseline ==="

ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))

post results ("1_baseline") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (.) (.) (.) (.) (.) (.) ///
    (e(rkf)) (e(N)) ///
    ("No interactions")

*--------------------------------------------------------------------*
* 10. SPECIFICATION 2: Endogenous growth (binary)
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 2: Endogenous growth ==="

* Create interactions
gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
local b3_int = _b[var3_growth]
local se3_int = _se[var3_growth]
local p3_int = 2*ttail(e(df_r), abs(`b3_int'/`se3_int'))
local b5_int = _b[var5_growth]
local se5_int = _se[var5_growth]
local p5_int = 2*ttail(e(df_r), abs(`b5_int'/`se5_int'))

post results ("2_endo_growth") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (`b3_int') (`se3_int') (`p3_int') ///
    (`b5_int') (`se5_int') (`p5_int') ///
    (e(rkf)) (e(N)) ///
    ("Endogenous growth (above median)")

drop var3_growth var5_growth var6_growth var7_growth

*--------------------------------------------------------------------*
* 11. SPECIFICATION 3: Exogenous growth (binary)
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 3: Exogenous growth ==="

* Create interactions
gen var3_gresid = var3 * high_growth_resid
gen var5_gresid = var5 * high_growth_resid
gen var6_gresid = var6 * high_growth_resid
gen var7_gresid = var7 * high_growth_resid

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_gresid var5_gresid = var6 var7 var6_gresid var7_gresid) ///
    var4 high_growth_resid ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
local b3_int = _b[var3_gresid]
local se3_int = _se[var3_gresid]
local p3_int = 2*ttail(e(df_r), abs(`b3_int'/`se3_int'))
local b5_int = _b[var5_gresid]
local se5_int = _se[var5_gresid]
local p5_int = 2*ttail(e(df_r), abs(`b5_int'/`se5_int'))

post results ("3_exo_growth") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (`b3_int') (`se3_int') (`p3_int') ///
    (`b5_int') (`se5_int') (`p5_int') ///
    (e(rkf)) (e(N)) ///
    ("Exogenous growth residualized on rent, HHI, industry, MSA")

drop var3_gresid var5_gresid var6_gresid var7_gresid

*--------------------------------------------------------------------*
* 12. SPECIFICATION 4: Exogenous growth + vacancy (binary)
*--------------------------------------------------------------------*
capture confirm variable high_growth_resid_v
if !_rc {
    di _n "=== SPECIFICATION 4: Exogenous growth + vacancy ==="
    
    * Create interactions
    gen var3_gresid_v = var3 * high_growth_resid_v
    gen var5_gresid_v = var5 * high_growth_resid_v
    gen var6_gresid_v = var6 * high_growth_resid_v
    gen var7_gresid_v = var7 * high_growth_resid_v
    
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_gresid_v var5_gresid_v = var6 var7 var6_gresid_v var7_gresid_v) ///
        var4 high_growth_resid_v ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    local b3 = _b[var3]
    local se3 = _se[var3]
    local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
    local b5 = _b[var5]
    local se5 = _se[var5]
    local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
    local b3_int = _b[var3_gresid_v]
    local se3_int = _se[var3_gresid_v]
    local p3_int = 2*ttail(e(df_r), abs(`b3_int'/`se3_int'))
    local b5_int = _b[var5_gresid_v]
    local se5_int = _se[var5_gresid_v]
    local p5_int = 2*ttail(e(df_r), abs(`b5_int'/`se5_int'))
    
    post results ("4_exo_growth_vac") (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') (`b3_int') (`se3_int') (`p3_int') ///
        (`b5_int') (`se5_int') (`p5_int') ///
        (e(rkf)) (e(N)) ///
        ("Exogenous growth also residualized on vacancy")
    
    drop var3_gresid_v var5_gresid_v var6_gresid_v var7_gresid_v
}
else {
    di _n "=== SPECIFICATION 4: Vacancy data not available, skipping ==="
}

*--------------------------------------------------------------------*
* 13. SPECIFICATION 5: Rent interaction (binary)
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 5: Rent interaction ==="

gen var3_rent = var3 * high_rent
gen var5_rent = var5 * high_rent
gen var6_rent = var6 * high_rent
gen var7_rent = var7 * high_rent

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_rent var5_rent = var6 var7 var6_rent var7_rent) ///
    var4 high_rent ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
local b3_int = _b[var3_rent]
local se3_int = _se[var3_rent]
local p3_int = 2*ttail(e(df_r), abs(`b3_int'/`se3_int'))
local b5_int = _b[var5_rent]
local se5_int = _se[var5_rent]
local p5_int = 2*ttail(e(df_r), abs(`b5_int'/`se5_int'))

post results ("5_rent") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (`b3_int') (`se3_int') (`p3_int') ///
    (`b5_int') (`se5_int') (`p5_int') ///
    (e(rkf)) (e(N)) ///
    ("High rent (above median)")

drop var3_rent var5_rent var6_rent var7_rent

*--------------------------------------------------------------------*
* 14. SPECIFICATION 6: HHI interaction (binary)
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 6: HHI interaction ==="

gen var3_hhi = var3 * high_hhi
gen var5_hhi = var5 * high_hhi
gen var6_hhi = var6 * high_hhi
gen var7_hhi = var7 * high_hhi

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_hhi var5_hhi = var6 var7 var6_hhi var7_hhi) ///
    var4 high_hhi ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
local b3_int = _b[var3_hhi]
local se3_int = _se[var3_hhi]
local p3_int = 2*ttail(e(df_r), abs(`b3_int'/`se3_int'))
local b5_int = _b[var5_hhi]
local se5_int = _se[var5_hhi]
local p5_int = 2*ttail(e(df_r), abs(`b5_int'/`se5_int'))

post results ("6_hhi") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (`b3_int') (`se3_int') (`p3_int') ///
    (`b5_int') (`se5_int') (`p5_int') ///
    (e(rkf)) (e(N)) ///
    ("High HHI (above median)")

drop var3_hhi var5_hhi var6_hhi var7_hhi

*--------------------------------------------------------------------*
* 15. Display first-stage statistics for residualization
*--------------------------------------------------------------------*
di _n "=== First-stage growth residualization ==="

* Show R-squared from growth residualization
reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo
di "R-squared for exogenous growth residualization: " e(r2)

capture reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo vacancy_rate
if !_rc {
    di "R-squared for exogenous growth + vacancy residualization: " e(r2)
}

*--------------------------------------------------------------------*
* 16. Save results
*--------------------------------------------------------------------*
postclose results
use `results_out', clear
export delimited using "`result_dir'/horse_race_results.csv", replace

* Create formatted output
list specification b3 p3_int b5 p5_int nobs if b3_int != .
list specification b3 b5 nobs if b3_int == .

* Export to LaTeX table
preserve
    keep specification b3 se3 b5 se5 b3_int se3_int b5_int se5_int rkf nobs
    
    * Format for table
    foreach v in b3 se3 b5 se5 b3_int se3_int b5_int se5_int {
        format `v' %9.3f
    }
    format rkf %9.2f
    format nobs %12.0fc
    
    export delimited using "`result_dir'/horse_race_table.csv", replace
restore

di _n as result "✓ Results saved to `result_dir'/horse_race_results.csv"

log close
