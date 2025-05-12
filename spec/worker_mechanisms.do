
//productivty and dispersion
//median split at user level 
//no bootstrap



do "../globals2.do"
//
********************************************************************************
* Define paths + specification name
********************************************************************************



local specname   "user_mechanisms"
local output_path "$results/`specname'"
capture mkdir "`output_path'"


* Ensure top-level folder exists
capture mkdir "`output_path'"
capture mkdir "`output_path'/OLS"
capture mkdir "`output_path'/IV"

********************************************************************************
* Data Preparation
********************************************************************************

* Load user-level contributions data
use "$scoop/Contributions_Scoop.dta", clear

gsort user_id year month

* Keep only "active" users
by user_id: egen any_contributions = max(totalcontribution)
gen active = any_contributions > 0
drop if active == 0

* Convert monthly to half-year 
gen half = ceil(month/6)

* Create a half-year index (yh) and format it
gen yh = yh(year, half)
format yh %th

* Collapse to user_id-yh level
collapse (sum) totalcontribution (sum) restrictedcontributionscount ///
         (first) companyname, ///
         by(user_id yh)

label var totalcontribution             "Total Contributions"
label var restrictedcontributionscount  "Pvt Contributions"

tempfile user_yh
save `user_yh', replace

********************************************************************************
* Merge firm-level characteristics into worker-level data
********************************************************************************
import delimited "$scoop/Scoop_Positions_Firm_Collapse2.csv", clear

* Converting date to Stata format and creating half-year indicators:
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

sort companyname date

* Drop last date
drop if date == 22797     

collapse (mean) total_employees, by(companyname)

tempfile company_emp
save `company_emp', replace

use `user_yh', clear

* Employee Counts
merge m:1 companyname using `company_emp'
drop if _merge != 3
drop _merge

* Teleworkable
merge m:1 companyname using "$scoop/scoop_firm_tele_2.dta"
drop if _merge != 3
drop _merge

* Merge with flexibility measures (e.g., remote/flexibility scores):
merge m:1 companyname using "$scoop/Scoop_clean_public.dta"
drop if _merge != 3
drop _merge

* Merge with founding year data:
merge m:1 companyname using "$scoop/Scoop_founding.dta"
drop if _merge != 3
drop _merge

* Compute firm age and encode IDs:
gen age = 2020 - founded
label var age "Firm age as of 2020"
encode companyname, gen(firm_id)

* Define startup indicator (age ≤ 10) and COVID period indicator (yh≥120):
gen startup = (age <= 10)
gen covid = yh >= 120

* rename remote variable
rename flexibility_score2 remote
rename restrictedcontributionscount restrictedcontributions

sort user_id yh

* Drop observations outside period of interest
// drop if yh < yh(2017,1) | yh > yh(2021,2)

********************************************************************************
* Save the "clean" final dataset for subsequent loops
********************************************************************************
tempfile snapshot_clean
save `snapshot_clean', replace




********************************************************************************
* 5) Merge Hierarchy Data (Centrality/HHI Analysis)
********************************************************************************
use "$data/Firm_role_level.dta", clear

* Compute the median of hhi_1000 (using quietly to suppress output)
// quietly summarize hhi_1000, detail
// local med_hhi1000 = r(p50)

* Create a binary indicator: 1 = High centrality (hhi_1000 above median), 0 = Low
// gen high_hhi1000 = (hhi_1000 > `med_hhi1000')


keep companyname hhi_1000 seniority_levels

merge 1:m companyname using `snapshot_clean'
drop if _merge == 1
drop _merge
gen seniority_4 = 0
replace seniority_4 = 1 if seniority_levels == 4

save `snapshot_clean', replace




use "/Users/saul/Dropbox/Remote Work Startups/New/Data/Leases/data_20240523_lease.dta", clear
// use "$data/data_20240523_lease.dta", clear
drop id_Lease

gen half = ceil(execution_month/6)
gen yh  = yh(execution_year, half)
format yh %th

// Weighted collapse by transaction sqft or whichever your approach
drop if yh < yh(2020, 1)
collapse (mean) effectiverent2212usdperyear [fweight=transactionsqft], by(city state)

// Clean city/state strings
gen hqcity  = strtrim(city)
gen hqstate = strtrim(state)

// Sort for merging
sort hqcity hqstate

tempfile _lease

save `_lease', replace

// Return to your working dataset in memory
use `snapshot_clean', clear 




merge m:1 hqcity hqstate using `_lease'
drop if _merge == 2
drop _merge



// rename effectiverent2212usdperyear to just rent for short
rename effectiverent2212usdperyear rent




save `snapshot_clean', replace






di as text ">> Enforcing BALANCED PANEL"
local panel_suffix "balanced"


* 1) Figure out the global min and max 'yh'
summarize yh
local global_min = r(min)
local global_max = r(max)


* 2) For each firm, find min_yh, max_yh, count of observations
bys user_id: egen min_time = min(yh)
bys user_id: egen max_time = max(yh)
bys user_id: egen nobs = count(yh)

* 3) Figure out how many half-years in the entire sample
preserve
contract yh, freq(count_yh)
local total_periods = _N
restore

di "Min Time: `global_min'"
di "Max Time: `global_max'"
di "Total Periods: `total_periods'"

* 4) Keep only those firms that have no "gaps" from global_min to global_max
keep if min_time == `global_min' ///
& max_time == `global_max' ///
& nobs == `total_periods'

drop min_time max_time nobs

gen pre_covid = (yh < 120)
by user_id: egen pre_covid_rest = total(cond(pre_covid == 1 & restrictedcontributions != ., restrictedcontributions, 0))

keep if pre_covid_rest > 0
local cond_suffix "rest_pre"


// gen var3 = remote * covid
// gen var4 = covid  * startup
// gen var5 = remote * covid * startup
// gen var6 = covid  * teleworkable
// gen var7 = startup * covid * teleworkable



local original_outcomes "totalcontribution restrictedcontributions"


foreach var of local original_outcomes {

	* Create percentile rank 1–100 by half-year
	bysort yh: egen `var'_q_100 = xtile(`var'), nq(100)

	local transformed_outcomes `transformed_outcomes' `var'_q_100
	label var `var'_q_100 "`var'_q (Percentile rank [1–100])"
}



*--------------------------------------------------------
* Panel A: OLS and Panel B: IV with Additional Interactions
* Baseline: 
*   var3 = covid * remote
*   var4 = covid * startup
*   var5 = covid * remote * startup
* Instruments:
*   var6 = covid * teleworkable  (for var3)
*   var7 = covid * startup * teleworkable  (for var5)
*
* Additional interactions:
*   Rent:
*     var8 = covid * rent          (exogenous)
*     var9 = covid * rent * remote (endogenous)
*     var10 = teleworkable * covid * rent (instrument for var9)
*
*   Centrality:
*     var11 = covid * hhi1000           (exogenous)
*     var12 = covid * hhi1000 * remote  (endogenous)
*     var13 = teleworkable * covid * hhi1000 (instrument for var12)
*
* The four columns are:
*   Col 1: Baseline only.
*   Col 2: Baseline + Rent interactions.
*   Col 3: Baseline + Centrality interactions.
*   Col 4: Baseline + Both Rent and Centrality interactions.
*--------------------------------------------------------

*==============================
* Define Baseline Variables
*==============================
gen var3 = covid * remote              // Baseline: covid x remote (endogenous)
gen var4 = covid * startup             // Baseline: covid x startup (exogenous)
gen var5 = covid * remote * startup    // Baseline: covid x remote x startup (endogenous)

* Instruments for baseline endogenous variables
gen var6 = covid * teleworkable         // Instrument for var3
gen var7 = covid * startup * teleworkable  // Instrument for var5

*==============================
* Define Rent-related Interactions
*==============================
gen var8 = covid * rent                // covid x rent (exogenous)
gen var9 = covid * rent * remote       // covid x rent x remote (endogenous)
gen var10 = teleworkable * covid * rent  // Instrument for var9

*==============================
* Define Centrality-related Interactions
*==============================
gen var11 = covid * hhi_1000              // covid x centrality (exogenous)
gen var12 = covid * hhi_1000 * remote     // covid x centrality x remote (endogenous)
gen var13 = teleworkable * covid * hhi_1000 // Instrument for var12



*==============================
* Define Centrality-related Interactions
*==============================
gen var14 = covid * seniority_4              
gen var15 = covid * seniority_4 * remote    
gen var16 = teleworkable * covid * seniority_4 




drop if missing(var3, var4, var5, var6, var7)


/*
*==============================
* Panel A: OLS Specifications
*==============================
* Column 1: Baseline only
reghdfe totalcontribution_q_100 ///
    var3 var4 var5, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "OLS_results.tex", replace ctitle("Col 1: Baseline") tex keep(var3 var5) 

* Column 2: Baseline + Rent interactions (adds var8 and var9)
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 ///
    var8 var9, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "OLS_results.tex", append ctitle("Col 2: + Rent") tex keep(var3 var5) 

* Column 3: Baseline + Centrality interactions (adds var11 and var12)
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 ///
    var11 var12, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "OLS_results.tex", append ctitle("Col 3: + Centrality") tex keep(var3 var5) 



* Column 3: Baseline + Seniority interactions (adds var14 and var15)
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 ///
    var14 var15, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "OLS_results.tex", append ctitle("Col 3: + Centrality") tex keep(var3 var5) 



* Column 4: Baseline + Both Rent + Centrality interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 ///
    var8 var9 ///
    var11 var12, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "OLS_results.tex", append ctitle("Col 4: + Both Rent + Centrality") tex keep(var3 var5) 


*/

*--------------------------------------------------------
* Example OLS Regressions for All Combinations
* Baseline: var3, var4, var5 (always included)
* Additional sets:
*   Rent:         var8, var9
*   Centrality:   var11, var12
*   Seniority:    var14, var15
*--------------------------------------------------------

* Column 1: Baseline only
reghdfe totalcontribution_q_100 ///
    var3 var4 var5, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", replace ctitle("Col 1: Baseline") tex keep(var3 var5)

* Column 2: Baseline + Rent interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var8 var9, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 2: + Rent") tex keep(var3 var5)

* Column 3: Baseline + Centrality interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var11 var12, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 3: + Centrality") tex keep(var3 var5)

* Column 4: Baseline + Seniority interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var14 var15, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 4: + Seniority") tex keep(var3 var5)

* Column 5: Baseline + Rent + Centrality interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var8 var9 var11 var12, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 5: + Rent + Centrality") tex keep(var3 var5)

* Column 6: Baseline + Rent + Seniority interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var8 var9 var14 var15, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 6: + Rent + Seniority") tex keep(var3 var5)

* Column 7: Baseline + Centrality + Seniority interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var11 var12 var14 var15, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 7: + Centrality + Seniority") tex keep(var3 var5)

* Column 8: Baseline + Rent + Centrality + Seniority interactions
reghdfe totalcontribution_q_100 ///
    var3 var4 var5 var8 var9 var11 var12 var14 var15, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/OLS_results.tex", append ctitle("Col 8: + Rent + Centrality + Seniority") tex keep(var3 var5)

*--------------------------------------------------------
* End of OLS combinations script
*--------------------------------------------------------






*------------------------------------------------------------
* Panel B: IV Specifications – All Combination of Interactions
*------------------------------------------------------------

* Column 1: Baseline IV only
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", replace ///
    ctitle("Col 1: Baseline") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 2: Baseline + Rent interactions
* Endogenous: var3, var5, var9; Instruments: var6, var7, var10; Exog: var4, var8
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var9 = var6 var7 var10) ///
    var4 var8, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 2: + Rent") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 3: Baseline + HHI-based Centrality interactions
* Endogenous: var3, var5, var12; Instruments: var6, var7, var13; Exog: var4, var11
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var12 = var6 var7 var13) ///
    var4 var11, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 3: + HHI") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 4: Baseline + Seniority-based Centrality interactions
* Endogenous: var3, var5, var15; Instruments: var6, var7, var16; Exog: var4, var14
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var15 = var6 var7 var16) ///
    var4 var14, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 4: + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 5: Baseline + Rent + HHI-based Centrality interactions
* Endogenous: var3, var5, var9, var12; Instruments: var6, var7, var10, var13; Exog: var4, var8, var11
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var9 var12 = var6 var7 var10 var13) ///
    var4 var8 var11, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 5: + Rent + HHI") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 6: Baseline + Rent + Seniority-based Centrality interactions
* Endogenous: var3, var5, var9, var15; Instruments: var6, var7, var10, var16; Exog: var4, var8, var14
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var9 var15 = var6 var7 var10 var16) ///
    var4 var8 var14, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 6: + Rent + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 7: Baseline + HHI-based + Seniority-based Centrality interactions
* Endogenous: var3, var5, var12, var15; Instruments: var6, var7, var13, var16; Exog: var4, var11, var14
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var12 var15 = var6 var7 var13 var16) ///
    var4 var11 var14, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 7: + HHI + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 8: Baseline + Rent + HHI-based + Seniority-based Centrality interactions
* Endogenous: var3, var5, var9, var12, var15; Instruments: var6, var7, var10, var13, var16; Exog: var4, var8, var11, var14
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var9 var12 var15 = var6 var7 var10 var13 var16) ///
    var4 var8 var11 var14, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "`output_path'/IV_results.tex", append ///
    ctitle("Col 8: + Rent, HHI + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

	


/*
*==============================
* Panel B: IV Specifications
*==============================
* Column 1: Baseline IV
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "IV_results.tex", replace ctitle("Col 1: Baseline") tex keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 2: Baseline + Rent interactions IV
*   Endogenous variables: var3, var5, and var9; instruments: var6, var7, and var10.
*   Exogenous: var4 and var8.
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var9 = var6 var7 var10) ///
    var4 var8, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "IV_results.tex", append ctitle("Col 2: + Rent") tex keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 3: Baseline + Centrality interactions IV
*   Endogenous variables: var3, var5, and var12; instruments: var6, var7, and var13.
*   Exogenous: var4 and var11.
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var12 = var6 var7 var13) ///
    var4 var11, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "IV_results.tex", append ctitle("Col 3: + Centrality") tex keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 4: Baseline + Both Rent + Centrality interactions IV
*   Endogenous variables: var3, var5, var9, and var12; instruments: var6, var7, var10, and var13.
*   Exogenous: var4, var8, and var11.
ivreghdfe totalcontribution_q_100 ///
    (var3 var5 var9 var12 = var6 var7 var10 var13) ///
    var4 var8 var11, ///
    absorb(user_id firm_id yh) ///
    vce(cluster user_id)
outreg2 using "IV_results.tex", append ctitle("Col 4: + Both Rent + Centrality") tex keep(var3 var5) addstat("KP rk Wald F", e(rkf))
*/


*--------------------------------------------------------
* End of Analysis Script
*--------------------------------------------------------



