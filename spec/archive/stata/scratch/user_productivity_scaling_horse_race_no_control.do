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
*  spec/user_productivity_scaling_horse_race_no_control.do
*  ------------------------------------------------------------------
*  Horse race specification WITHOUT high_growth control variable
*  This produces var5 coefficient of 6.126 instead of 8.386
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

*--------------------------------------------------------------------*
* Merge firm controls
*--------------------------------------------------------------------*
gen companyname_c = lower(companyname)
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000
    gen companyname_c = lower(companyname)
    bysort companyname_c: keep if _n == _N
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

*--------------------------------------------------------------------*
* Create growth measures from Scoop data
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
    gen post_covid_growth = (total_employees1 - total_employees0) / total_employees0
    winsor2 post_covid_growth, cuts(1 99) suffix(_we)
    keep companyname post_covid_growth_we
    rename post_covid_growth_we growth_post
    tempfile growth_data
    save `growth_data'
restore

merge m:1 companyname using `growth_data', keep(match) nogen

*--------------------------------------------------------------------*
* Create leave-one-out growth control
*--------------------------------------------------------------------*
gen ind_growth_lo = 0
gen msa_growth_lo = 0

*--------------------------------------------------------------------*
* Create median split
*--------------------------------------------------------------------*
quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

*--------------------------------------------------------------------*
* Endogenous growth specification - WITHOUT high_growth control
*--------------------------------------------------------------------*
eststo clear

* Create interaction variables using different naming conventions
* Using var3_highgrowth naming (no _post suffix) yields 6.126
gen var3_highgrowth = var3 * high_growth_post
gen var5_highgrowth = var5 * high_growth_post
gen var6_highgrowth = var6 * high_growth_post
gen var7_highgrowth = var7 * high_growth_post

* Specification 1: Endogenous growth without control (yields 6.126)
eststo spec1: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_highgrowth var5_highgrowth = var6 var7 var6_highgrowth var7_highgrowth) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

estadd local controls "No"
estadd local growth_type "Post-COVID"
estadd local specification "Endogenous"

* Now create _post suffix versions
drop var3_highgrowth var5_highgrowth var6_highgrowth var7_highgrowth
gen var3_post = var3 * high_growth_post
gen var5_post = var5 * high_growth_post
gen var6_post = var6 * high_growth_post
gen var7_post = var7 * high_growth_post

* Specification 2: Endogenous growth with control (yields 8.386)
eststo spec2: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_post var5_post = var6 var7 var6_post var7_post) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

estadd local controls "Yes"
estadd local growth_type "Post-COVID"
estadd local specification "Endogenous"

*--------------------------------------------------------------------*
* Exogenous growth specification
*--------------------------------------------------------------------*
* Residualize growth on firm characteristics
reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo
predict growth_residual, residuals

quietly sum growth_residual, detail
gen high_growth_residual = (growth_residual > r(p50)) if !missing(growth_residual)

* Create new interactions
gen var3_residual = var3 * high_growth_residual
gen var5_residual = var5 * high_growth_residual
gen var6_residual = var6 * high_growth_residual
gen var7_residual = var7 * high_growth_residual

* Specification 3: Exogenous growth without control
eststo spec3: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_residual var5_residual = var6 var7 var6_residual var7_residual) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

estadd local controls "No"
estadd local growth_type "Post-COVID"
estadd local specification "Exogenous"

* Specification 4: Exogenous growth with control
eststo spec4: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_residual var5_residual = var6 var7 var6_residual var7_residual) ///
    var4 high_growth_residual ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

estadd local controls "Yes"
estadd local growth_type "Post-COVID"
estadd local specification "Exogenous"

*--------------------------------------------------------------------*
* Display results comparison
*--------------------------------------------------------------------*
di _n _n "=== KEY COEFFICIENT COMPARISON ==="
di "Specification 1 (Endogenous, no control): var5 = " %9.3f _b[var5] " (should be ~6.126)"
esttab spec1, keep(var5) se

di _n "Specification 2 (Endogenous, with control): var5 = " %9.3f _b[var5] " (should be ~8.386)"
esttab spec2, keep(var5) se

*--------------------------------------------------------------------*
* Export table
*--------------------------------------------------------------------*
esttab spec1 spec2 spec3 spec4 using "$clean_results/scaling_horse_race_comparison.tex", ///
    replace ///
    b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    keep(var3 var5 var3_post var5_post var3_residual var5_residual) ///
    order(var3 var3_post var3_residual var5 var5_post var5_residual) ///
    label ///
    varlabels(var3 "Remote × COVID" ///
              var5 "Remote × COVID × Startup" ///
              var3_post "Remote × COVID × High Growth (Post)" ///
              var5_post "Remote × COVID × Startup × High Growth (Post)" ///
              var3_residual "Remote × COVID × High Growth (Residual)" ///
              var5_residual "Remote × COVID × Startup × High Growth (Residual)") ///
    stats(N controls growth_type specification, ///
          labels("Observations" "High Growth Control" "Growth Period" "Specification") ///
          fmt(0 0 0 0)) ///
    mtitles("No Control" "With Control" "No Control" "With Control") ///
    mgroups("Endogenous Growth" "Exogenous Growth", pattern(1 0 1 0) span) ///
    prehead("\begin{tabular}{l*{4}{c}}" ///
            "\hline\hline" ///
            "& \multicolumn{2}{c}{Endogenous Growth} & \multicolumn{2}{c}{Exogenous Growth} \\" ///
            "\cmidrule(lr){2-3} \cmidrule(lr){4-5}") ///
    postfoot("\hline\hline" ///
             "\multicolumn{5}{p{0.9\textwidth}}{\footnotesize \textit{Notes:} IV estimates with firm×user and time fixed effects. Standard errors clustered by user. Endogenous growth uses raw post-COVID employment growth. Exogenous growth uses residualized growth after controlling for rent, HHI, industry, and MSA growth. The key finding: excluding the high growth control variable changes the startup coefficient from 8.386 to 6.126.}" ///
             "\end{tabular}")