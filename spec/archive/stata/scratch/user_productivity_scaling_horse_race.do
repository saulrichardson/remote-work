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
log using "$LOG_DIR/scaling_horse_race.log", replace text




*====================================================================*
*  spec/user_productivity_scaling_horse_race.do
*  ------------------------------------------------------------------
*  Tests multiple theories about what drives remote work productivity:
*    1. Endogenous (post-COVID) scaling
*    2. Exogenous (pre-COVID) scaling  
*    3. Vacancies as additional instruments
*    4. Interactions with rent, HHI, tightness
*    5. Predictive growth regressions
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
* 2. Calculate PRE-COVID growth (exogenous scaling)
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
    
    * Keep only pre-COVID data
    keep if yh < 120  // Before 2020h1
    
    * Calculate 2019 growth
    collapse (last) total_employees, by(companyname yh)
    
    encode companyname, gen(firm_n)
    xtset firm_n yh
    
    * Get 2019h1 and 2019h2 employment
    gen emp_2019h1 = total_employees if yh == 118
    gen emp_2019h2 = total_employees if yh == 119
    
    collapse (max) emp_2019h1 emp_2019h2, by(companyname)
    
    gen growth_2019 = (emp_2019h2 - emp_2019h1) / emp_2019h1 if !missing(emp_2019h1, emp_2019h2)
    winsor2 growth_2019, cuts(1 99) suffix(_we)
    
    keep companyname growth_2019_we
    rename growth_2019_we growth_pre
    tempfile pre_growth
    save `pre_growth'
restore

*--------------------------------------------------------------------*
* 3. Calculate POST-COVID growth (endogenous scaling) 
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
    
    drop if date == 22797
    
    collapse (last) total_employees date, by(companyname yh)
    
    gen byte covid = (yh >= 120)
    
    * Static growth measure
    tempfile base_collapse
    save `base_collapse'
    
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
* 4. Get vacancy data and other measures
*--------------------------------------------------------------------*
* Merge growth measures
merge m:1 companyname using `pre_growth', keep(match) nogen
merge m:1 companyname using `post_growth', keep(match) nogen

* Try to merge vacancy data
capture preserve
capture import delimited "$processed_data/vacancy_measures_2020.csv", clear
if !_rc {
    tempfile vacancy
    save `vacancy'
    restore
    capture merge m:1 companyname using `vacancy', keep(match master)
    if !_rc {
        drop if _rc == 0
        drop _merge
    }
}
else {
    capture restore
}

* Get labor market tightness
preserve
    import delimited "$processed_data/firm_tightness_static.csv", clear
    rename companyname companyname_c
    tempfile tight
    save `tight'
restore
merge m:1 companyname_c using `tight', keep(match master) nogen

*--------------------------------------------------------------------*
* 5. Setup results tracking
*--------------------------------------------------------------------*
local result_dir "$results/scaling_horse_race_`panel_variant'"
cap mkdir "`result_dir'"

tempfile results_out
capture postclose results
postfile results ///
    str32 specification ///
    double b3 se3 p3 /// base remote effect
    double b5 se5 p5 /// startup-remote effect  
    double rkf nobs ///
    str100 notes ///
    using `results_out', replace

*--------------------------------------------------------------------*
* 6. SPECIFICATION 1: Baseline (no growth control)
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
    (`b5') (`se5') (`p5') (e(rkf)) (e(N)) ///
    ("No growth controls")

*--------------------------------------------------------------------*
* 7. SPECIFICATION 2: Endogenous (post-COVID) growth
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 2: Post-COVID growth ==="

* Create interactions
gen var3_post = var3 * growth_post
gen var5_post = var5 * growth_post
gen var6_post = var6 * growth_post
gen var7_post = var7 * growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_post var5_post = var6 var7 var6_post var7_post) ///
    var4 c.growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))

post results ("2_post_growth") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (e(rkf)) (e(N)) ///
    ("Endogenous post-COVID growth interaction")

drop var3_post var5_post var6_post var7_post

*--------------------------------------------------------------------*
* 8. SPECIFICATION 3: Exogenous (pre-COVID) growth
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 3: Pre-COVID growth ==="

* Create interactions
gen var3_pre = var3 * growth_pre
gen var5_pre = var5 * growth_pre
gen var6_pre = var6 * growth_pre
gen var7_pre = var7 * growth_pre

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_pre var5_pre = var6 var7 var6_pre var7_pre) ///
    var4 c.growth_pre ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))

post results ("3_pre_growth") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (e(rkf)) (e(N)) ///
    ("Exogenous pre-COVID growth interaction")

drop var3_pre var5_pre var6_pre var7_pre

*--------------------------------------------------------------------*
* 9. SPECIFICATION 4: Vacancy in first stage (if available)
*--------------------------------------------------------------------*
capture confirm variable vacancy_rate
if !_rc {
    di _n "=== SPECIFICATION 4: Vacancy in first stage ==="
    
    ivreghdfe total_contributions_q100 ///
        (var3 var5 = var6 var7 vacancy_rate) ///
        var4 ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    local b3 = _b[var3]
    local se3 = _se[var3]
    local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
    local b5 = _b[var5]
    local se5 = _se[var5]
    local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))
    
    post results ("4_vacancy_iv") (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') (e(rkf)) (e(N)) ///
        ("Vacancy rate as additional instrument")
}
else {
    di _n "=== SPECIFICATION 4: Vacancy data not available, skipping ==="
}

*--------------------------------------------------------------------*
* 10. SPECIFICATION 5: Rent interaction
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 5: Rent interaction ==="

* Standardize rent for interpretation
egen rent_std = std(rent)

gen var3_rent = var3 * rent_std
gen var5_rent = var5 * rent_std
gen var6_rent = var6 * rent_std
gen var7_rent = var7 * rent_std

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_rent var5_rent = var6 var7 var6_rent var7_rent) ///
    var4 c.rent_std ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

local b3 = _b[var3]
local se3 = _se[var3]
local p3 = 2*ttail(e(df_r), abs(`b3'/`se3'))
local b5 = _b[var5]
local se5 = _se[var5]
local p5 = 2*ttail(e(df_r), abs(`b5'/`se5'))

post results ("5_rent") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (e(rkf)) (e(N)) ///
    ("Rent interaction (standardized)")

drop var3_rent var5_rent var6_rent var7_rent rent_std

*--------------------------------------------------------------------*
* 11. SPECIFICATION 6: HHI interaction
*--------------------------------------------------------------------*
di _n "=== SPECIFICATION 6: HHI interaction ==="

* Create high concentration dummy
quietly sum hhi_1000, detail
gen high_hhi = (hhi_1000 > r(p50)) if !missing(hhi_1000)

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

post results ("6_hhi") (`b3') (`se3') (`p3') ///
    (`b5') (`se5') (`p5') (e(rkf)) (e(N)) ///
    ("High HHI interaction (above median)")

drop var3_hhi var5_hhi var6_hhi var7_hhi high_hhi

*--------------------------------------------------------------------*
* 12. Predictive growth regression
*--------------------------------------------------------------------*
di _n "=== Predictive growth regression ==="

reg growth_post growth_pre startup age rent hhi_1000 if !missing(growth_post, growth_pre)
est store growth_pred

outreg2 using "`result_dir'/growth_predictors.tex", ///
    replace tex label ///
    title("Predictors of Post-COVID Firm Growth") ///
    addtext(Sample, Pre-COVID panel firms) ///
    dec(3)

*--------------------------------------------------------------------*
* 13. Save results
*--------------------------------------------------------------------*
postclose results
use `results_out', clear
export delimited using "`result_dir'/horse_race_results.csv", replace

* Create summary table
list specification b3 p3 b5 p5 nobs

di _n as result "✓ Results saved to `result_dir'/horse_race_results.csv"

log close
