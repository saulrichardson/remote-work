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
*  spec/test_winsor_median.do
*  ------------------------------------------------------------------
*  Test exact differences in growth variable construction
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* Load and prepare base data
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

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
* Calculate growth variable and test different approaches
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
    collapse (mean) total_employees, by(companyname covid)
    reshape wide total_employees, i(companyname) j(covid)
    
    * Calculate raw growth
    gen growth_raw = (total_employees1 - total_employees0) / total_employees0
    
    * Test different winsorization approaches
    winsor2 growth_raw, cuts(1 99) suffix(_w1)
    
    * Check statistics
    di _n "=== GROWTH VARIABLE STATISTICS ==="
    sum growth_raw, detail
    local med_raw = r(p50)
    
    sum growth_raw_w1, detail
    local med_w1 = r(p50)
    
    di "Raw growth median: " `med_raw'
    di "Winsorized growth median: " `med_w1'
    
    * Create binary indicators with different medians
    gen high_raw = (growth_raw > `med_raw') if !missing(growth_raw)
    gen high_w1 = (growth_raw_w1 > `med_w1') if !missing(growth_raw_w1)
    
    * Also test if they're using the median of the winsorized variable
    sum growth_raw_w1, detail
    gen high_w1_med = (growth_raw_w1 > r(p50)) if !missing(growth_raw_w1)
    
    * Compare distributions
    tab high_raw high_w1
    tab high_w1 high_w1_med
    
    keep companyname growth_raw growth_raw_w1 high_raw high_w1 high_w1_med
    rename growth_raw_w1 growth_post
    tempfile growth_data
    save `growth_data'
restore

merge m:1 companyname using `growth_data', keep(match) nogen

*--------------------------------------------------------------------*
* Test each approach
*--------------------------------------------------------------------*
foreach var in high_raw high_w1 high_w1_med {
    
    gen var3_g = var3 * `var'
    gen var5_g = var5 * `var'
    gen var6_g = var6 * `var'
    gen var7_g = var7 * `var'
    
    di _n "=== TESTING WITH `var' ==="
    
    * Distribution check
    tab `var'
    
    * Run regression
    ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_g var5_g = var6 var7 var6_g var7_g) ///
        var4 `var' ///
        , absorb(firm_id#user_id yh) ///
        vce(cluster user_id)
    
    di "`var' - var5 coefficient: " %9.3f _b[var5]
    
    drop var3_g var5_g var6_g var7_g
}

*--------------------------------------------------------------------*
* Also check if it's about the variable name itself
*--------------------------------------------------------------------*
di _n "=== TESTING EXACT HORSE RACE VARIABLE NAME ==="

* Create high_growth_post from growth_post
quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

tab high_growth_post

ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di "Exact horse race approach - var5 coefficient: " %9.3f _b[var5]

*--------------------------------------------------------------------*
* Compare the actual growth values
*--------------------------------------------------------------------*
di _n "=== GROWTH VARIABLE COMPARISON ==="
sum growth_raw growth_post
corr growth_raw growth_post
tab high_w1_med high_growth_post