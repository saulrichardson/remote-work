********************************************************************************
* SCRIPT: Merge Teleworkability Data, Expand to Month, Collapse to 
*         Half-Year Periods, and Generate Half-Year Time Variable (yh)
********************************************************************************

do "../../spec/stata/_bootstrap.do"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/build_linkedin_panel.log", replace text
*---------------------------------------------------------*
* 1) Load the LinkedIn Positions Data & Standardize SOC Codes
*---------------------------------------------------------*
use "$raw_data/Scoop_workers_positions_filtered.dta", clear

* (For ad-hoc testing, you can temporarily filter on a user_id here.)
* keep if user_id == 1001643

* Create a standardized occupation code (soc_new).
* Use soc_2010 if available; if empty, replace with soc6d.
gen soc_new = soc_2010
replace soc_new = soc6d if (soc_new == "")

* Save the dataset to a temporary file for later merging.
tempfile tf_linkedin_occupation
save `tf_linkedin_occupation', replace

********************************************************************************
* 2) Import and Clean ONET Teleworkability Data
********************************************************************************
import delimited "$raw_data/occupations_workathome.csv", clear stringcols(_all)

* Convert teleworkable to numeric.
destring teleworkable, replace

* Clean up the ONET occupation codes:
replace onetsoccode = strtrim(onetsoccode)
gen before_dot = substr(onetsoccode, 1, 7)  // e.g., "15-1130"
gen after_dot  = substr(onetsoccode, 8, .)   // e.g., ".00"
keep if after_dot == ".00"                  // Keep only codes ending in ".00"
rename before_dot soc_new                   // Rename to match LinkedIn data

* Save the cleaned ONET data to a temporary file.
tempfile tf_onet
save `tf_onet', replace

********************************************************************************
* 3) Merge ONET Teleworkability Data with LinkedIn Data
********************************************************************************
use `tf_onet', clear
merge 1:m soc_new using `tf_linkedin_occupation'

* Drop ONET records that did not match any LinkedIn data.
drop if _merge == 1  
drop _merge

* Save the partially merged results.
tempfile tf_soc_partial
save `tf_soc_partial', replace

********************************************************************************
* 4) Collapse Teleworkability by Role (role_k1000)
********************************************************************************
preserve
    * Drop observations missing a role or occupation code.
    drop if role_k1000 == "" 
    drop if soc_new == ""
    
    * Collapse data by role_k1000 to compute the mean teleworkable score.
    collapse (mean) teleworkable, by(role_k1000)
    
    * Save the role-level teleworkability data.
    tempfile tf_tele_by_role
    save `tf_tele_by_role', replace
restore  // Return to the partial-merged dataset

********************************************************************************
* 5) Merge Role-Level Teleworkability Back into Main Data
********************************************************************************
merge m:1 role_k1000 using `tf_tele_by_role', update

* Drop observations that did not match a role.
drop if _merge == 1  
drop _merge

* Optionally, filter out roles you do not want.
drop if role_k1000 == "10.0"
drop if role_k1000 == "7.0"


drop employeecount flexibilitylevelclean officerequirementsclean daysoftheweekclean mindaysweekclean oftimeclean flexibility_score flexibility_score1 flex_days flexibility_score2 flexibility_score3
********************************************************************************
* 6) Expand Each Job Spell to One Row per Month
********************************************************************************

* Convert date strings to Stata date values (adjust mask "YMD" if needed).
gen start = date(start_date, "YMD")
gen end   = date(end_date, "YMD")
format start %td
format end   %td

* Convert daily dates to monthly dates using mofd() (month of date).
gen start_mon = mofd(start)
gen end_mon   = mofd(end)
format start_mon %tm
format end_mon   %tm

* Expand each observation so that each job spell yields one row per month.
expand end_mon - start_mon + 1

* Within each job spell, generate the monthly date for the current record.
bysort user_id start_mon end_mon: gen mon = start_mon + _n - 1
format mon %tm

********************************************************************************
* 7) Generate Half-Year Variables and Collapse to One Record per Half-Year (yh)
********************************************************************************

* Convert the monthly date (mon) to a daily date (using dofm) so we can extract year/month.
gen mon_day = dofm(mon)
format mon_day %td

* Extract calendar year and month from mon_day.
gen y = year(mon_day)
gen m = month(mon_day)

* Determine half-year indicator: 
*   half = 0 if month is January–June, 1 if month is July–December.
gen half = (m >= 7)

* Create a string representation of the half-year period (e.g., "2015H1" or "2015H2").
gen yh_str = string(y) + cond(half==0, "H1", "H2")

* Generate a numeric half-year identifier.
* Here we use: yh = (year - 1900)*2 + half
* (Adjust the base year as needed to match the other dataset.)
gen yh = cond(half == 0, yh(y, 1), yh(y, 1))
format yh %th

* Collapse to one record per user_id and half-year (yh), keeping all variables using the (last) option.

********************************************************************************
* 7B) Alternate Collapse: Keep All Variables Except the Ones to Drop
********************************************************************************
* Suppose you do not want to keep these variables:
local dropvars user_id yh

* Create a local macro that lists all variables except those in dropvars.
ds `dropvars', not
local keepvars `r(varlist)'

* Collapse the dataset by user_id and yh, taking the last observation in each group.
collapse (last) `keepvars', by(user_id yh)


********************************************************************************
* 8) (Optional) Save the Final Dataset
********************************************************************************
* Remove any variables you don't want to keep (if needed).
* (For example, the previous version dropped several variables; here we keep all.)
save "$processed_data/expanded_half_years.dta", replace

log close
