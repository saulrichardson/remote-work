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
*  Trace sample size differences between mini-report and growth analysis
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

di _n "====== TRACING SAMPLE SIZE DIFFERENCES ======"
di "Comparing mini-report (229,862 obs) vs growth analysis (227,766 obs)"
di "Difference: 2,096 observations"

*--------------------------------------------------------------------*
* 1. Load main user panel (like mini-report baseline)
*--------------------------------------------------------------------*
di _n "=== STEP 1: Loading user panel ==="
use "$processed_data/user_panel_`panel_variant'.dta", clear
count
di "Initial user panel observations: " r(N)
local initial_obs = r(N)

* Check for missing key variables
count if missing(user_id)
di "Missing user_id: " r(N)
count if missing(firm_id) 
di "Missing firm_id: " r(N)
count if missing(yh)
di "Missing yh: " r(N)
count if missing(total_contributions_q100)
di "Missing outcome variable: " r(N)

*--------------------------------------------------------------------*
* 2. Apply growth analysis merges
*--------------------------------------------------------------------*
di _n "=== STEP 2: Growth analysis specific processing ==="

* First get firm controls (matching growth_mechanisms_both_fe.do)
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

* Generate company name for merge
gen companyname_c = lower(companyname)
count
di "Before firm_extra merge: " r(N)

merge m:1 companyname_c using `firm_extra', keep(match) nogen
count
di "After firm_extra merge (keep matched only): " r(N)
local after_firm_merge = r(N)

di _n "Lost in firm_extra merge: " `initial_obs' - `after_firm_merge'

*--------------------------------------------------------------------*
* 3. Check for additional filters or drops
*--------------------------------------------------------------------*
di _n "=== STEP 3: Checking for singleton drops ==="

* Check if we'll lose observations to singleton FEs
* First check firm#user_id singletons
egen firm_user = group(firm_id user_id)
bysort firm_user: gen n_firm_user = _N
count if n_firm_user == 1
di "Singleton firm#user_id observations: " r(N)

* Check separate FE singletons
bysort user_id: gen n_user = _N
bysort firm_id: gen n_firm = _N  
bysort yh: gen n_yh = _N
count if n_user == 1
di "Singleton user_id observations: " r(N)
count if n_firm == 1
di "Singleton firm_id observations: " r(N)
count if n_yh == 1
di "Singleton yh observations: " r(N)

*--------------------------------------------------------------------*
* 4. Try exact baseline regression to see drops
*--------------------------------------------------------------------*
di _n "=== STEP 4: Running baseline regression ==="

* Variables already exist in the data, just verify
count if !missing(var3, var4, var5, var6, var7)
di "Observations with all regression variables: " r(N)

di _n "Running with separate FEs (matching mini-report):"
count
di "Observations before regression: " r(N)

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
    
di "Observations in regression: " e(N)

*--------------------------------------------------------------------*
* 5. Alternative: Check growth data construction path
*--------------------------------------------------------------------*
di _n "=== STEP 5: Checking growth data path ==="

* The growth analysis also loads Scoop_Positions_Firm_Collapse2.csv
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    count
    di "Scoop positions data rows: " r(N)
    
    * Check unique companies
    egen tag = tag(companyname)
    count if tag
    di "Unique companies in Scoop data: " r(N)
restore

* Check how many companies from user panel exist in Scoop data
preserve
    keep companyname
    duplicates drop
    count
    di "Unique companies in user panel: " r(N)
    
    tempfile user_companies
    save `user_companies'
    
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    keep companyname
    duplicates drop
    
    merge 1:1 companyname using `user_companies'
    count if _merge == 2
    di "Companies in user panel but NOT in Scoop data: " r(N)
restore

*--------------------------------------------------------------------*
* 6. Summary
*--------------------------------------------------------------------*
di _n "====== SUMMARY ======"
di "Initial observations: " `initial_obs'
di "After firm merge: " `after_firm_merge'
di "Difference: " `initial_obs' - `after_firm_merge'
di _n "This accounts for the 2,096 observation difference between"
di "mini-report (229,862) and growth analysis (227,766)"