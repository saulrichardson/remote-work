*----------------------------------------------------------------------
* heterogeneity_growth_base.do  —  IV split by post-shock labor-growth
*   base controls: var3  var4
*----------------------------------------------------------------------
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


// Collapse to have one observation per firm-half-year, and calculate growth & rates:
collapse (last) total_employees date (sum) join leave, by(companyname yh)


encode companyname, gen(company_numeric)
xtset company_numeric yh
sort company_numeric yh

gen growth_rate = (total_employees / L.total_employees) - 1 if _n > 1


xtset, clear

winsor2 growth_rate, cuts(1 99) suffix(_we)
label variable growth_rate_we "Winsorized growth rate [1,99]"


drop growth_rate  company_numeric

rename growth_rate_we growth_yh


keep companyname yh growth_yh

*──────── 4.  Save to a tempfile for later merge ───────────────────────*
tempfile firm_growth          // temp filename macro
save `firm_growth', replace   // dataset lives only this session

restore


*--------------------------------------------------------------*
*  Merge firm-level growth into the user panel in memory       *
*--------------------------------------------------------------*
merge m:1 companyname yh using `firm_growth', nogenerate  


drop if missing(growth_yh)

*--------------------------------------------------------------*
*  Build growth terciles **within each half-year (yh)**        *
*--------------------------------------------------------------*
preserve
    keep companyname yh growth_yh
    duplicates drop companyname yh, force          // 1 row per firm-yh

    * 1) rank within the half-year -----------------------------
    bys yh: egen _r = rank(growth_yh)                // 1 … _N inside yh

    * 2) turn rank into tercile -------------------------------
    bys yh: gen  lg_tile = ceil(3 * _r / _N)         // 1 = low, 3 = high
    drop _r

    keep companyname yh lg_tile
    tempfile gtiles
    save `gtiles'
restore

* attach the tercile code to every worker-half-year row
merge m:1 companyname yh using `gtiles', nogenerate





*--------------------------------------------------------------*
*  Logging & postfile setup                                    *
*--------------------------------------------------------------*
cap mkdir "log"
capture log close
log using "log/dynamic_het_growth_base.log", replace text

local result_dir "$results/dynamic_growth_base_`panel_variant'"
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
foreach g in 1 2 3{

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
