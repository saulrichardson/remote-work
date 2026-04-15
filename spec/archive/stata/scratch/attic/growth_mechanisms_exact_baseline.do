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
*  Growth mechanisms with exact baseline replication
*  Uses relaxed merge to preserve all observations for baseline
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* 1. Load main user panel data
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
count
di "Initial observations: " r(N)

*--------------------------------------------------------------------*
* 2. Get firm controls with RELAXED merge (keep all observations)
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

gen companyname_c = lower(companyname)

* RELAXED MERGE - keep all observations, just flag missing
merge m:1 companyname_c using `firm_extra', keep(1 3) nogen

* Flag observations with missing growth controls
gen has_growth_controls = !missing(rent, hhi_1000)
count
di "After relaxed merge: " r(N)
count if has_growth_controls
di "Observations with growth controls: " r(N)

tempfile main_panel
save `main_panel'

*--------------------------------------------------------------------*
* 3. Run baseline regression with ALL observations
*--------------------------------------------------------------------*
di _n "=== BASELINE WITH ALL OBSERVATIONS (Matching Mini-Report) ==="

* Run with separate FEs to match mini-report exactly
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id) savefirst

* Save results
eststo clear
eststo baseline_all
estadd scalar rkf = e(rkf), replace

* Also run with firm#user FE for comparison
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
    
eststo baseline_all_firmuser
estadd scalar rkf = e(rkf), replace

*--------------------------------------------------------------------*
* 4. Construct growth measures (only for observations with controls)
*--------------------------------------------------------------------*
* Now work with subset that has growth controls for growth regressions
keep if has_growth_controls

import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
format yh %th

drop if date == 22797

collapse (last) total_employees date (sum) join leave, by(companyname yh)

gen byte covid = (yh >= 120)

* Calculate growth rates
preserve
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    
    * Create ENDOGENOUS growth tile (raw)
    xtile tile_post_c = growth_rate_we_post_c, nq(2)
    
    tempfile g_postavg
    save `g_postavg'
restore

*--------------------------------------------------------------------*
* 5. Build residualized growth (matching original script line 281)
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname industry
    gen company_msa = "all"
    bysort companyname: keep if _n == 1
    tempfile firmkeys
    save `firmkeys'
restore

preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi = hhi_1000, nq(2)
    tempfile firm_extra2
    save `firm_extra2'
restore

* Build leave-one-out growth rates
merge m:1 companyname using `firmkeys', nogenerate
encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh
gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)
keep if covid
tempfile postcovid
save `postcovid'

* Industry leave-one-out
use `postcovid', clear
bys industry: egen ind_sum = total(fg_we)
bys industry: egen ind_N = count(fg_we)
gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

* MSA leave-one-out (placeholder since all same MSA)
use `postcovid', clear
bys company_msa: egen msa_sum = total(fg_we)
bys company_msa: egen msa_N = count(fg_we)
gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
keep company_msa msa_growth_postavg_lo
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

* Merge and run residualization
use `postcovid', clear
gen companyname_c = lower(companyname)
merge m:1 industry using `ind_postavg', keep(match) nogen
merge m:1 company_msa using `msa_postavg', keep(match) nogen
merge m:1 companyname using `g_postavg', keep(match) nogen
merge m:1 companyname_c using `firm_extra2', keep(match) nogen

* This matches line 281 of original script
reg growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi
predict growth_resid

* Create EXOGENOUS growth tile (fitted values)
xtile tile_growth_resid = growth_resid, nq(2)

* Keep only firm-level growth info
keep companyname tile_post_c tile_growth_resid
duplicates drop
tempfile growth_tiles
save `growth_tiles'

*--------------------------------------------------------------------*
* 6. Merge growth back to user panel (subset with controls)
*--------------------------------------------------------------------*
use `main_panel', clear
keep if has_growth_controls

merge m:1 companyname using `growth_tiles', keep(match) nogen

* Create interaction variables
gen var17 = var3 * (tile_post_c == 2)
gen var18 = var5 * (tile_post_c == 2)
gen var19 = var3 * (tile_growth_resid == 2)
gen var20 = var5 * (tile_growth_resid == 2)

*--------------------------------------------------------------------*
* 7. Run growth specifications (subset only)
*--------------------------------------------------------------------*
di _n "=== GROWTH SPECIFICATIONS (Subset with Controls) ==="

* Endogenous growth with separate FE
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(user_id firm_id yh) vce(cluster user_id) savefirst
eststo endog_separate
estadd scalar rkf = e(rkf), replace

* Exogenous growth with separate FE
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var19 var20, ///
    absorb(user_id firm_id yh) vce(cluster user_id) savefirst
eststo
estadd scalar rkf = e(rkf), replace exog_separate

* Endogenous growth with firm#user FE
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
eststo
estadd scalar rkf = e(rkf), replace endog_firmuser

* Exogenous growth with firm#user FE
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var19 var20, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
eststo
estadd scalar rkf = e(rkf), replace exog_firmuser

*--------------------------------------------------------------------*
* 8. Display results
*--------------------------------------------------------------------*
di _n _n "====== SUMMARY OF RESULTS ======"
di "Baseline with all obs (separate FE): Should match mini-report's 9.94"
di "Baseline with all obs (firm#user FE): For comparison"
di "Growth specifications use only subset with controls"

esttab baseline_all baseline_all_firmuser endog_separate exog_separate endog_firmuser exog_firmuser, ///
    keep(var3 var5) ///
    b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    stats(N rkf, fmt(%9.0fc %9.1f) labels("Observations" "KP F-stat")) ///
    mtitles("Baseline All" "Baseline All FU" "Endog Sep" "Exog Sep" "Endog FU" "Exog FU") ///
    nonotes