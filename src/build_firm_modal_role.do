********************************************************************************
** 0) Initial Setup
********************************************************************************

do "../globals.do"

********************************************************************************
** 1) Import LinkedIn Occupation Data
********************************************************************************

import delimited "$data/Scoop_workers_positions.csv", clear bindquote(strict) ///
    stringcols(_all)
    
* Convert date strings to Stata date values.
gen start = date(start_date, "YMD")
gen end   = date(end_date, "YMD")
format start %td
format end   %td


local cutoff = date("2019-12-31", "YMD")
keep if start <= `cutoff' & (missing(end) | end >= `cutoff')


order companyname role_k7
bysort companyname role_k7 : gen _freq = _N      
* Order so that the most frequent role comes first
gsort companyname -_freq role_k7                
* Within each firm, keep only the first (i.e. modal) role
bysort companyname : keep if _n == 1
* Keep only what you need
keep companyname role_k7 _freq

save "$data/modal_role_per_firm.dta", replace


