do "../src/globals.do"

capture log close
cap mkdir "log"
log using "log/build_panel_og.log", replace text

*----------------------------------------------------------
* User-Level Contributions
*----------------------------------------------------------
use "$processed_data/Contributions_Scoop.dta", clear
gsort user_id year month
by user_id: egen any_contributions = max(totalcontribution)
gen active = any_contributions > 0
drop if active == 0

* Convert monthly to half-year indicators:
gen half = ceil(month/6)
gen yh = yh(year, half)
format yh %th

* Collapse to user_id–yh level:
collapse (sum) totalcontribution (sum) restrictedcontributionscount ///
         (first) companyname, by(user_id yh)
label var totalcontribution             "Total Contributions"
label var restrictedcontributionscount  "Pvt Contributions"

drop if yh > yh(2022, 1)

tempfile user_yh
save `user_yh', replace

*----------------------------------------------------------
* Adding 2022h1 User-Level Contributions
*----------------------------------------------------------

* Recent contributions data
import delimited "$raw_data/MonthlyContributions.csv", clear

tostring monthyear, replace format(%06.0f)
gen year  = substr(monthyear, 1, 4)
gen month = substr(monthyear, 5, 2)

destring year month, replace

gen half = ceil(month/6)
gen yh = yh(year, half)
format yh %th


collapse (sum) totalcontribution (sum) restrictedcontributionscount, by(user_id yh)
label var totalcontribution             "Total Contributions"
label var restrictedcontributionscount  "Pvt Contributions"

keep if yh == yh(2022, 1)

tempfile user_yh_new
save `user_yh_new', replace

* Linkedn panel for users in the data 
use "$processed_data/expanded_half_years_2.dta", clear
keep if yh == yh(2022, 1)

keep user_id companyname yh

* Attach company name to each user
duplicates tag user_id yh, generate(dup_tag)

keep if dup_tag == 0

merge 1:1 user_id yh using `user_yh_new'
keep if _merge == 3
drop _merge

append using `user_yh'
save `user_yh', replace


*----------------------------------------------------------
* Merge Firm-Level Characteristics into Worker Data
*----------------------------------------------------------

* Merge teleworkable information:
merge m:1 companyname using "$processed_data/scoop_firm_tele_2.dta"
tab _merge
drop if _merge != 3
drop _merge
rename teleworkable company_teleworkable

* Merge with flexibility scores:
merge m:1 companyname using "$raw_data/Scoop_clean_public.dta"
tab _merge
drop if _merge != 3
drop _merge

* Merge with founding year:
merge m:1 companyname using "$raw_data/Scoop_founding.dta"
tab _merge
drop if _merge != 3
drop _merge

* Merge back in linkedin data to enforce ground truth (contributions data had 
* imputed some company names where there were gaps in linkedin)
merge 1:1 user_id companyname yh using"$processed_data/expanded_half_years_2.dta"
tab _merge
drop if _merge != 3
drop _merge


tempfile snapshot_clean
save `snapshot_clean', replace

* Merge Hierarchy Data (Centrality/HHI Analysis)
use "$processed_data/Firm_role_level.dta", clear
keep companyname hhi_1000 seniority_levels

merge 1:m companyname using `snapshot_clean'
tab _merge
drop if _merge == 1. //drop if company not found in the worker panel
drop _merge

save `snapshot_clean', replace


use "$raw_data/data_20240523_lease.dta", clear
drop id_Lease

gen half = ceil(execution_month/6)
gen yh  = yh(execution_year, half)
format yh %th

keep if yh < yh(2020, 1)
collapse (mean) effectiverent2212usdperyear [fweight=transactionsqft], by(city state)


gen hqcity  = strtrim(city)
gen hqstate = strtrim(state)
sort hqcity hqstate

tempfile _lease
save `_lease', replace


use `snapshot_clean', clear 
merge m:1 hqcity hqstate using `_lease'
tab _merge
drop if _merge == 2. //drop if hqcity-hqstate not found in leasing data
drop _merge

rename effectiverent2212usdperyear rent

* Merge firm modal role 
merge m:1 companyname using "$processed_data/modal_role_per_firm.dta"
drop if _merge == 2   
drop _merge

* Merge worker modal role 
merge m:1 user_id using "$processed_data/worker_baseline_role"
drop if _merge == 2     
drop _merge

* Merge Wage dispersion 
merge m:1 companyname using "$processed_data/wages_firm.dta"
drop if _merge == 2    // drop observations that only exist in using data
drop _merge


gen age = 2020 - founded
label var age "Firm age as of 2020"
encode companyname, gen(firm_id)
gen startup = (age <= 10)
gen covid = yh >= 120
rename flexibility_score2 remote
rename restrictedcontributionscount restricted_contributions
rename totalcontribution  total_contributions


sort user_id yh

* Restricted on pre-covid restricted contributions
gen pre_covid = (yh < 120)
by user_id: egen pre_covid_rest = total(cond(pre_covid == 1 & restricted_contributions != ., restricted_contributions, 0))


* Enforce balanced panel 
gsort user_id yh
summarize yh
local global_min = r(min)
local global_max = r(max)
by user_id: egen min_time = min(yh)
by user_id: egen max_time = max(yh)
by user_id: egen nobs = count(yh)
preserve
    contract yh, freq(count_yh)
    local total_periods = _N
restore
keep if min_time == `global_min'  & max_time == `global_max' & nobs == `total_periods'
drop min_time max_time nobs

* Keep only users with positive pre-COVID restricted contributions
keep if pre_covid_rest > 0

* Create IV variables:
gen var3 = remote * covid
gen var4 = covid * startup
gen var5 = remote * covid * startup
gen var6 = covid * company_teleworkable
gen var7 = startup * covid * company_teleworkable

* Define the original outcomes:
local original_outcomes "total_contributions restricted_contributions"
local transformed_outcomes ""

* Transform outcomes (winsorize and create percentile ranks):
foreach var of local original_outcomes {
    winsor2 `var', cuts(5 95) suffix(_we)
    bysort yh: egen `var'_q100 = xtile(`var'), nq(100)
    label var `var'_we    "`var' (Winsorized [5–95])"
    label var `var'_q100 "`var' (Percentile rank [1–100])"
}

*----------------------------------------------------------
*  Common-sample flag (drop rows with ANY missing values)
*----------------------------------------------------------
local keep_vars ///
    user_id firm_id yh covid remote startup company_teleworkable ///
    total_contributions_q100 restricted_contributions_q100 ///
    var3 var4 var5 var6 var7

* Count how many of those variables are missing in each row
egen miss_ct = rowmiss(`keep_vars')

* Keep rows with zero missing values
gen  byte common_sample = (miss_ct == 0)   // 1 = complete row
count if common_sample == 0
local n_drop = r(N)

di as error "Dropping `n_drop' observation(s) with missing values for variables: `keep_vars'"


keep if common_sample == 1
drop miss_ct common_sample                              


save "$processed_data/user_panel.dta", replace

log close
// export delimited "../data/samples/user_panel.csv", replace
