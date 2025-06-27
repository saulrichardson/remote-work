*----------------------------------------------------------------------
* heterogeneity_growth_base.do  —  IV split by post-shock labor-growth
*   base controls: var3  var4
*----------------------------------------------------------------------
* ---------------------------------------------------------------------
*  User-configurable parameters
* ---------------------------------------------------------------------
local nbins 3                      // number of growth buckets (e.g., 2 or 3)

args panel_variant
if "`panel_variant'"=="" local panel_variant "precovid"

use "$processed_data/user_panel_`panel_variant'.dta", clear

*----------------------------------------------------------------------
* 1.  Build firm-level growth-rate terciles (1 = low, 3 = high)
*----------------------------------------------------------------------
*---------------------------------------------------------------
*  After: collapse total_employees by(companyname yh)
*---------------------------------------------------------------

preserve


import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th

// Drop one-off observations in June 2022
drop if date == 22797

gen byte covid = yh >= 120     // 1 = post-COVID (2020H1+), 0 = pre

collapse (mean) total_employees, by(companyname covid)


reshape wide total_employees, i(companyname) j(covid)

rename total_employees0 emp_pre        // average employees pre-COVID
rename total_employees1 emp_post       // average employees post-COVID

/**************************************************************************
*  4.  Compute growth measures
**************************************************************************/
gen growth_abs  = emp_post - emp_pre                     // absolute change
gen post_covid_growth  = (emp_post - emp_pre) / emp_pre  if !missing(emp_pre, emp_post) // percent change



winsor2 post_covid_growth, cuts(1 99) suffix(_we)

keep companyname post_covid_growth_we
rename post_covid_growth_we post_covid_growth
label var post_covid_growth ///
      "Winsorised firm growth: mean post-COVID ÷ mean pre-COVID – 1  (1-99 %)"

*──────── 4.  Save to a tempfile for later merge ───────────────────────*
tempfile firm_growth          // temp filename macro
save `firm_growth', replace   // dataset lives only this session

restore


*--------------------------------------------------------------*
*  Merge firm-level growth into the user panel in memory       *
*--------------------------------------------------------------*
merge m:1 companyname using `firm_growth', nogenerate   // adds post_covid_growth



*--------------------------------------------------------------*
*  Build growth terciles (1 = low, 3 = high)                   *
*--------------------------------------------------------------*
preserve
    keep companyname post_covid_growth
    duplicates drop companyname, force
    xtile lg_tile = post_covid_growth, nq(`nbins')
    keep companyname lg_tile
    tempfile gtiles
    save `gtiles'
restore

merge m:1 companyname using `gtiles', nogenerate       // attach lg_tile to every row

*--------------------------------------------------------------*
*  Logging & postfile setup                                    *
*--------------------------------------------------------------*
cap mkdir "log"
capture log close
log using "log/post_het_growth_base.log", replace text

local result_dir "$results/post_growth_base_`panel_variant'_`nbins'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str8   bucket       ///  1, 2, 3
    double coef3 se3 pval3   /// var3 stats
    double coef5 se5 pval5   /// var5 stats
    double rkf nobs          /// first‐stage F and N
    using `out', replace

*--------------------------------------------------------------*
*  Loop over growth buckets, run base-spec IV                  *
*--------------------------------------------------------------*
forvalues g = 1/`nbins' {

    di as text "=== growth bucket `g' ==="

    ivreghdfe total_contributions_q100                 ///
        (var3 var5 = var6 var7) var4                  ///
        if lg_tile == `g',                             ///
        absorb(firm_id#user_id yh) vce(cluster user_id) savefirst

    // compute stats for var3
    local b3   = _b[var3]
    local se3  = _se[var3]
    local p3   = 2*ttail(e(df_r), abs(`b3'/`se3'))

    // compute stats for var5
    local b5   = _b[var5]
    local se5  = _se[var5]
    local p5   = 2*ttail(e(df_r), abs(`b5'/`se5'))

    post handle ("`g'") ///
        (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') ///
        (e(rkf)) (e(N))

}

postclose handle
use `out', clear
export delimited using "`result_dir'/var5_growth_base.csv", replace

log close
