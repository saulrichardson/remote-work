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
*  Investigate why there are duplicates in the firm growth data
*====================================================================*

do "../globals.do"

* Load the Scoop data and trace through the transformations
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td
gen yh = hofd(date)
format yh %th
drop if date == 22797

* First, let's see the structure before collapse
di _n "=== BEFORE COLLAPSE ==="
di "Number of observations: " _N
count
bysort companyname yh: gen obs_per_firm_yh = _N
tab obs_per_firm_yh if obs_per_firm_yh > 1

* Collapse to firm-half-year level
collapse (last) total_employees date (sum) join leave, by(companyname yh)
gen byte covid = (yh >= 120)

di _n "=== AFTER COLLAPSE ==="
di "Number of observations: " _N
count

* Check for duplicates at firm-half-year level
duplicates report companyname yh
duplicates tag companyname yh, gen(dup_firm_yh)
tab dup_firm_yh

* Now let's trace what happens when we calculate growth and keep only COVID period
encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh
gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
winsor2 growth_yh, cuts(1 99) suffix(_we)

* Calculate average post-COVID growth
preserve
    keep if covid
    collapse (mean) growth_yh_we, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    
    di _n "=== FIRM-LEVEL GROWTH (one obs per firm) ==="
    count
    duplicates report companyname
restore

* Keep only COVID period data
keep if covid

di _n "=== POST-COVID FIRM-HALF-YEAR DATA ==="
di "Number of observations: " _N
count
bysort companyname: gen obs_per_firm = _N
tab obs_per_firm

* Show some examples of firms with multiple observations
di _n "=== EXAMPLES OF FIRMS WITH MULTIPLE POST-COVID OBSERVATIONS ==="
list companyname yh total_employees growth_yh_we in 1/20

* Count unique firms
egen tag = tag(companyname)
count if tag
di "Number of unique firms: " r(N)

* Now let's see what happens when we merge this with leave-one-out calculations
* Get firm keys
preserve
    collapse (last) industry (last) company_msa, by(companyname)
    tempfile firmkeys
    save `firmkeys'
restore

merge m:1 companyname using `firmkeys', nogenerate

* Check the data structure after merge
di _n "=== AFTER MERGING FIRM KEYS ==="
count
bysort companyname: gen obs_after_merge = _N
tab obs_after_merge

* This is where the "duplicates" come from - we have multiple half-years per firm
di _n "=== STRUCTURE OF DATA FOR REGRESSION ==="
di "Each row is a firm-half-year observation in the post-COVID period"
di "For the first-stage regression, we have:"
bysort companyname: gen half_years_per_firm = _N
tab half_years_per_firm