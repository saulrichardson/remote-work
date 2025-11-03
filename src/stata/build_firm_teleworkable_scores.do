do "../../spec/stata/_bootstrap.do"

capture log close
cap mkdir "log"
log using "log/build_firm_teleworkable_scores.log", replace text


import delimited "$raw_data/rolek1000_onet_cw.csv", varnames(1)  ///
    clear bindquote(strict) stringcols(_all)

rename onet_code new_onet_code
rename onet_title new_onet_title

tempfile new_onet
save `new_onet', replace


********************************************************************************
* Import LinkedIn Occupation Data
********************************************************************************

import delimited "$raw_data/Scoop_workers_positions.csv", clear bindquote(strict) ///
    stringcols(_all) 
    
* Standardize SOC codes: use soc_2010; if missing, use soc6d.
// gen soc_new = soc_2010
// replace soc_new = soc6d if (soc_new == "")

merge m:1 role_k1000 using `new_onet'
keep if _merge != 2 //gets rid of roles from onet that we dont have in linkedin
drop _merge

//assume new onset scores are full match and replace previous soc_new which
//serve as merging variable for teleworkable socre 

replace new_onet_code = strtrim(new_onet_code)
gen before_dot = substr(new_onet_code, 1, 7)  // e.g., "15-1130"
gen after_dot  = substr(new_onet_code, 8, .)   // e.g., ".00"
keep if after_dot == ".00"
rename before_dot new_onet_code_cleaned
rename new_onet_code_cleaned soc_new



tempfile tf_linkedin_occupation
save `tf_linkedin_occupation', replace

********************************************************************************
* Import ONET Teleworkability Data
********************************************************************************

import delimited "$raw_data/occupations_workathome.csv", clear stringcols(_all)
destring teleworkable, replace

// Clean up ONET codes.
replace onetsoccode = strtrim(onetsoccode)
gen before_dot = substr(onetsoccode, 1, 7)  // e.g., "15-1130"
gen after_dot  = substr(onetsoccode, 8, .)   // e.g., ".00"
keep if after_dot == ".00"
rename before_dot soc_new

// Save to a tempfile.
tempfile tf_onet
save `tf_onet', replace

********************************************************************************
* Merge LinkedIn with ONET Data
********************************************************************************

use `tf_onet', clear
merge 1:m soc_new using `tf_linkedin_occupation'

* Drop ONET records that did not match any LinkedIn observations.
drop if _merge == 1
drop _merge

* Save the merged (partial) results.
tempfile tf_soc_partial
save `tf_soc_partial', replace

********************************************************************************
* Collapse Teleworkability by Role (role_k1000)
********************************************************************************

preserve
    drop if role_k1000 == ""
    drop if soc_new == ""
    collapse (mean) teleworkable, by(role_k1000)
    tempfile tf_tele_by_role
    save `tf_tele_by_role', replace
restore

********************************************************************************
* Merge Role-Level Teleworkability Back into Main Data
********************************************************************************

merge m:1 role_k1000 using `tf_tele_by_role', update
drop if _merge == 1
drop _merge

// Optionally, filter out unwanted roles.
drop if role_k1000 == "10.0"
drop if role_k1000 == "7.0"

// Save the cleaned dataset.
tempfile tf_linkedin_full
save `tf_linkedin_full', replace

********************************************************************************
* Filter to Pre-COVID Job Spells 
********************************************************************************

use `tf_linkedin_full', clear

* Convert date strings to Stata date values.
gen start = date(start_date, "YMD")
gen end   = date(end_date, "YMD")
format start %td
format end   %td

* Drop observations with missing start or end dates.
drop if missing(start) | missing(end)

* 2 Year Window
local end_cutoff = date("2019-12-31", "YMD")
local start_cutoff = date("2017-12-31", "YMD")

* Keep only job spells that ended strictly before the cutoff.
keep if end >= `start_cutoff'
keep if start <= `end_cutoff'

********************************************************************************
* Collapse to Company Level (Firm-Level Teleworkability)
********************************************************************************

collapse (mean) teleworkable (first) company (first) final_parent_company, ///
    by(companyname)
drop if companyname == ""
keep companyname teleworkable

********************************************************************************
* Save the Final Dataset
********************************************************************************

save "$processed_data/scoop_firm_tele_2.dta", replace

log close

