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
*  spec/user_productivity_scaling_horse_race_full.do
*  ------------------------------------------------------------------
*  Full horse race specification with all columns:
*    1. Baseline (no interactions)
*    2. Endogenous growth (raw post-COVID growth)
*    3. Exogenous growth (residualized on rent, HHI, industry, MSA)
*    4. Exogenous growth + vacancy
*    5. Rent interaction
*    6. HHI interaction
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* Load and prepare data
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
* Calculate POST-COVID growth
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
    tempfile post_growth
    save `post_growth'
restore

merge m:1 companyname using `post_growth', keep(match) nogen

*--------------------------------------------------------------------*
* Get vacancy data (may not exist for all)
*--------------------------------------------------------------------*
capture {
    preserve
        import delimited "$processed_data/vacancy_data.csv", clear encoding(utf8)
        keep companyname vacancy_rate
        tempfile vacancy
        save `vacancy'
    restore
    merge m:1 companyname using `vacancy', keep(match master) nogen
}
if _rc {
    gen vacancy_rate = .
}

*--------------------------------------------------------------------*
* Create leave-one-out growth controls (placeholders if not available)
*--------------------------------------------------------------------*
gen ind_growth_lo = 0
gen msa_growth_lo = 0

*--------------------------------------------------------------------*
* Create all binary indicators
*--------------------------------------------------------------------*
* Growth measures
quietly sum growth_post, detail
gen high_growth_post = (growth_post > r(p50)) if !missing(growth_post)

* Residualized growth (without vacancy)
reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo
predict growth_resid, residuals
quietly sum growth_resid, detail
gen high_growth_resid = (growth_resid > r(p50)) if !missing(growth_resid)

* Residualized growth (with vacancy)
capture reg growth_post rent hhi_1000 ind_growth_lo msa_growth_lo vacancy_rate
if !_rc {
    predict growth_resid_v, residuals
    quietly sum growth_resid_v, detail
    gen high_growth_resid_v = (growth_resid_v > r(p50)) if !missing(growth_resid_v)
}
else {
    gen high_growth_resid_v = high_growth_resid
}

* Rent
quietly sum rent, detail
gen high_rent = (rent > r(p50)) if !missing(rent)

* HHI
quietly sum hhi_1000, detail
gen high_hhi = (hhi_1000 > r(p50)) if !missing(hhi_1000)

*--------------------------------------------------------------------*
* Run all specifications
*--------------------------------------------------------------------*
eststo clear

* Specification 1: Baseline (no interactions)
eststo spec1: ivreghdfe total_contributions_q100 ///
    (var3 var5 = var6 var7) ///
    var4 ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Specification 2: Endogenous growth
gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

eststo spec2: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Specification 3: Exogenous growth
gen var3_exo = var3 * high_growth_resid
gen var5_exo = var5 * high_growth_resid
gen var6_exo = var6 * high_growth_resid
gen var7_exo = var7 * high_growth_resid

eststo spec3: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_exo var5_exo = var6 var7 var6_exo var7_exo) ///
    var4 high_growth_resid ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Specification 4: Exogenous growth + vacancy
gen var3_exov = var3 * high_growth_resid_v
gen var5_exov = var5 * high_growth_resid_v
gen var6_exov = var6 * high_growth_resid_v
gen var7_exov = var7 * high_growth_resid_v

eststo spec4: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_exov var5_exov = var6 var7 var6_exov var7_exov) ///
    var4 high_growth_resid_v ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Specification 5: Rent interaction
gen var3_rent = var3 * high_rent
gen var5_rent = var5 * high_rent
gen var6_rent = var6 * high_rent
gen var7_rent = var7 * high_rent

eststo spec5: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_rent var5_rent = var6 var7 var6_rent var7_rent) ///
    var4 high_rent ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

* Specification 6: HHI interaction
gen var3_hhi = var3 * high_hhi
gen var5_hhi = var5 * high_hhi
gen var6_hhi = var6 * high_hhi
gen var7_hhi = var7 * high_hhi

eststo spec6: ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_hhi var5_hhi = var6 var7 var6_hhi var7_hhi) ///
    var4 high_hhi ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

*--------------------------------------------------------------------*
* Export results to CSV
*--------------------------------------------------------------------*
* Full results
esttab spec1 spec2 spec3 spec4 spec5 spec6 using "$results/scaling_horse_race_full.csv", ///
    replace ///
    cells(b(fmt(6)) se(fmt(6)) p(fmt(4))) ///
    stats(N r2_a, fmt(0 4)) ///
    plain

* Create summary CSV for key coefficients
file open summary using "$results/horse_race_full_summary.csv", write replace
file write summary "specification,var3_coef,var3_se,var5_coef,var5_se,var3_int_coef,var3_int_se,var5_int_coef,var5_int_se,N" _n

* Spec 1: Baseline
estimates restore spec1
file write summary "baseline," %9.6f (_b[var3]) "," %9.6f (_se[var3]) "," 
file write summary %9.6f (_b[var5]) "," %9.6f (_se[var5]) ",,,,," (e(N)) _n

* Spec 2: Endogenous
estimates restore spec2
file write summary "endogenous," %9.6f (_b[var3]) "," %9.6f (_se[var3]) "," 
file write summary %9.6f (_b[var5]) "," %9.6f (_se[var5]) ","
file write summary %9.6f (_b[var3_growth]) "," %9.6f (_se[var3_growth]) ","
file write summary %9.6f (_b[var5_growth]) "," %9.6f (_se[var5_growth]) "," (e(N)) _n

* Spec 3: Exogenous
estimates restore spec3
file write summary "exogenous," %9.6f (_b[var3]) "," %9.6f (_se[var3]) "," 
file write summary %9.6f (_b[var5]) "," %9.6f (_se[var5]) ","
file write summary %9.6f (_b[var3_exo]) "," %9.6f (_se[var3_exo]) ","
file write summary %9.6f (_b[var5_exo]) "," %9.6f (_se[var5_exo]) "," (e(N)) _n

* Spec 4: Exogenous + vacancy
estimates restore spec4
file write summary "exogenous_vacancy," %9.6f (_b[var3]) "," %9.6f (_se[var3]) "," 
file write summary %9.6f (_b[var5]) "," %9.6f (_se[var5]) ","
file write summary %9.6f (_b[var3_exov]) "," %9.6f (_se[var3_exov]) ","
file write summary %9.6f (_b[var5_exov]) "," %9.6f (_se[var5_exov]) "," (e(N)) _n

* Spec 5: Rent
estimates restore spec5
file write summary "rent," %9.6f (_b[var3]) "," %9.6f (_se[var3]) "," 
file write summary %9.6f (_b[var5]) "," %9.6f (_se[var5]) ","
file write summary %9.6f (_b[var3_rent]) "," %9.6f (_se[var3_rent]) ","
file write summary %9.6f (_b[var5_rent]) "," %9.6f (_se[var5_rent]) "," (e(N)) _n

* Spec 6: HHI
estimates restore spec6
file write summary "hhi," %9.6f (_b[var3]) "," %9.6f (_se[var3]) "," 
file write summary %9.6f (_b[var5]) "," %9.6f (_se[var5]) ","
file write summary %9.6f (_b[var3_hhi]) "," %9.6f (_se[var3_hhi]) ","
file write summary %9.6f (_b[var5_hhi]) "," %9.6f (_se[var5_hhi]) "," (e(N)) _n

file close summary

di _n "=== RESULTS EXPORTED ==="
di "Full results: $results/scaling_horse_race_full.csv"
di "Summary: $results/horse_race_full_summary.csv"