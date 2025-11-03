
do "../../spec/stata/_bootstrap.do"

capture log close
cap mkdir "log"
log using "log/build_firm_panel.log", replace text


import delimited "$raw_data/Scoop_alt.csv", clear

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th

collapse (last) date (sum) join leave, by(companyname yh)


keep companyname yh join leave
tempfile join_leave
save `join_leave'


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

drop join leave
merge 1:1 companyname yh using `join_leave'
drop _merge

encode companyname, gen(company_numeric)
xtset company_numeric yh
sort company_numeric yh

// gen growth_rate = (total_employees / L.total_employees) - 1 if _n > 1
// gen join_rate = join / L.total_employees if _n > 1
// gen leave_rate = leave / L.total_employees if _n > 1

gen total_employees_lag = L.total_employees


gen growth_rate = (total_employees/total_employees_lag) - 1   if total_employees_lag < .
gen join_rate   = join / total_employees_lag           if total_employees_lag < .
gen leave_rate  = leave/ total_employees_lag           if total_employees_lag < .

xtset, clear

winsor2 growth_rate join_rate leave_rate, cuts(1 99) suffix(_we)
label variable growth_rate_we "Winsorized growth rate [1,99]"
label variable join_rate_we "Winsorized join rate [1,99]"
label variable leave_rate_we "Winsorized leave rate [1,99]"

drop growth_rate join_rate leave_rate company_numeric


/*************************************************************************
 * 4) Merge firm-level characteristics into worker-level data
 *************************************************************************/

// Merge teleworkable data:
merge m:1 companyname using "$processed_data/scoop_firm_tele_2.dta"
drop if _merge == 2
drop _merge

// Merge with flexibility measures (e.g., remote/flexibility scores):
merge m:1 companyname using "$raw_data/Scoop_clean_public.dta"
drop if _merge == 2
drop _merge

// Merge with founding year data:
merge m:1 companyname using "$raw_data/Scoop_founding.dta"
drop if _merge == 2
drop _merge

tempfile snapshot_clean
save `snapshot_clean', replace


* Merge Hierarchy Data (Centrality/HHI Analysis)
use "$processed_data/Firm_role_level.dta", clear

keep companyname hhi_1000 seniority_levels

merge 1:m companyname using `snapshot_clean'
drop if _merge == 1 
drop _merge

save `snapshot_clean', replace


* Merge Rent Data 
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
egen hqID = group(hqcity hqstate), label
label var hqID "Unique numeric ID of HQ city & state"

tempfile _lease
save `_lease', replace


use `snapshot_clean', clear 

merge m:1 hqcity hqstate using `_lease'
drop if _merge == 2          
drop _merge                  

rename effectiverent2212usdperyear rent


* Merge firm modal role 
merge m:1 companyname using "$processed_data/modal_role_per_firm.dta"
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

gen byte hybrid    = (remote>0 & remote<1)
gen byte fullrem   = (remote==1)
gen byte inperson  = (remote==0)
gen byte nonrem    = inperson
gen byte anyremote = (remote>0)

* For the hybrid treatment
gen var3_hybrid = hybrid * covid
gen var5_hybrid = hybrid * covid * startup

* For the fully-remote treatment
gen var3_fullrem = fullrem * covid
gen var5_fullrem = fullrem * covid * startup

* For the in-person treatment (remote == 0)
gen var3_inperson = inperson * covid
gen var5_inperson = inperson * covid * startup

* For the legacy non-remote definition (synonym for in-person)
gen var3_nonrem = inperson * covid
gen var5_nonrem = inperson * covid * startup

* For any remote exposure (full-remote or hybrid)
gen var3_anyremote = anyremote * covid
gen var5_anyremote = anyremote * covid * startup


summarize yh
local global_min = r(min)
bys firm_id: egen min_time = min(yh)

preserve
    contract yh, freq(count_yh)
    local total_periods = _N
restore

keep if min_time == `global_min'
drop min_time

// Generate key interactions:
gen var3 = remote * covid
gen var4 = covid * startup
gen var5 = remote * covid * startup
gen var6 = covid * teleworkable
gen var7 = startup * covid * teleworkable


local keep_vars ///
    firm_id yh covid remote startup teleworkable ///
    growth_rate_we leave_rate_we join_rate_we ///
    var3 var4 var5 var6 var7

* Count how many of those variables are missing in each row
egen miss_ct = rowmiss(`keep_vars')

* Keep rows with zero missing values
gen  byte common_sample = (miss_ct == 0)   // 1 = complete row
count if common_sample == 0
di as error "Dropping " r(N) " observation(s) with missing values for variables: `keep_vars'"

keep if common_sample == 1
drop miss_ct common_sample    

save "$processed_data/firm_panel.dta", replace
export delimited "../data/samples/firm_panel.csv", replace

log close
