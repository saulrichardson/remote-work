/*-------------------------------------------------------------------
| build_user_panel.do — Generate user-level panel datasets
| Author : <your-name>
| Updated: 06 Jun 2025
|
| DESCRIPTION
| ----------
| Re-runs the *original* cleaning / merging pipeline **unchanged**, then
| branches into three sample variants **without touching any other
| logic**:
|   • unbalanced – full cleaned panel (default)
|   • balanced   – users observed in *every* half-year between the
|                  global min & max yh
|   • precovid   – users with positive pre-COVID restricted contributions
|
# NOTE ──────────────────────────────────────────────────────────────────
# In earlier versions the *pre-COVID* (“precovid”) sample was silently
# duplicated to the generic legacy filenames `user_panel.dta/csv`.  This
# implicit fallback made it impossible to see at a glance which panel
# variant later specification scripts had been run on.
#
# The compatibility artefact has now been **removed**: every output file
# is written *only* under an explicit, self-describing filename of the
# form `user_panel_<variant>.dta|csv` (e.g. `user_panel_unbalanced.dta`).
# Down-stream code must therefore always reference the panel variant
# explicitly in filenames (e.g. by passing it as an argument to
# specification scripts).  No more silent defaults.
|
| USAGE
| -----
|   do build_user_panel.do
|   *Optionally* edit `local sample_types` to generate a subset.
*-------------------------------------------------------------------*/

capture log close
cap mkdir "log"
log using "log/build_all_user_panels.log", replace text

****************************************************************************
* 0.  Globals
****************************************************************************
do "../src/globals.do"

****************************************************************************
* 1.  Build the *full* (unfiltered) master panel
****************************************************************************

*----------------------------------------------------------
* 1.1  User-level contributions (historic)
*----------------------------------------------------------
use "$processed_data/Contributions_Scoop.dta", clear

* drop inactive accounts --------------------------------------------------
gsort user_id year month
by user_id: egen any_contributions = max(totalcontribution)
keep if any_contributions

* derive half-year id ------------------------------------------------------
gen half = ceil(month/6)
gen yh   = yh(year, half)
format yh %th

* monthly → half-year collapse -------------------------------------------*
collapse (sum) totalcontribution (sum) restrictedcontributionscount ///
         (first) companyname, by(user_id yh)
label var totalcontribution            "Total Contributions"
label var restrictedcontributionscount "Pvt Contributions"

keep if yh <= yh(2022,1)

tempfile user_yh
save     "`user_yh'", replace

*----------------------------------------------------------
* 1.2  Add 2022 H1 contributions (monthly CSV)
*----------------------------------------------------------
import delimited "$raw_data/MonthlyContributions.csv", clear

tostring monthyear, replace format(%06.0f)
gen year  = substr(monthyear,1,4)
gen month = substr(monthyear,5,2)

destring year month, replace

gen half = ceil(month/6)
gen yh   = yh(year, half)
format yh %th

collapse (sum) totalcontribution (sum) restrictedcontributionscount, by(user_id yh)
keep if yh == yh(2022,1)
label var totalcontribution            "Total Contributions"
label var restrictedcontributionscount "Pvt Contributions"

tempfile user_yh_new
save     "`user_yh_new'", replace

* attach company names -----------------------------------------------------
use "$processed_data/expanded_half_years_2.dta", clear
keep if yh == yh(2022,1)
keep user_id companyname yh

duplicates tag user_id yh, gen(dup_tag)
keep if dup_tag==0

merge 1:1 user_id yh using "`user_yh_new'", keep(3) nogen

append using "`user_yh'"
save   "`user_yh'", replace


*----------------------------------------------------------
* 1.3  Merge firm-level characteristics (logic identical to original)
*----------------------------------------------------------
use "`user_yh'", clear

* teleworkability ---------------------------------------------------------*
merge m:1 companyname using "$processed_data/scoop_firm_tele_2.dta", keep(3) nogen
rename teleworkable company_teleworkable

* flexibility score -------------------------------------------------------*
merge m:1 companyname using "$raw_data/Scoop_clean_public.dta", keep(3) nogen

* founding year -----------------------------------------------------------*
merge m:1 companyname using "$raw_data/Scoop_founding.dta",     keep(3) nogen

* linkedin ground-truth ---------------------------------------------------*
merge 1:1 user_id companyname yh using "$processed_data/expanded_half_years_2.dta", keep(3) nogen

tempfile snapshot_clean
save     "`snapshot_clean'", replace

*----------------------------------------------------------
* 1.4  Hierarchy / HHI merge  (keep _merge==2|3)
*----------------------------------------------------------
use "$processed_data/Firm_role_level.dta", clear
keep companyname hhi_1000 seniority_levels

merge 1:m companyname using "`snapshot_clean'"
drop if _merge==1   // drop firms absent from worker panel
drop _merge

save "`snapshot_clean'", replace

*----------------------------------------------------------
* 1.5  Commercial real-estate rents  (keep _merge==1|3)
*----------------------------------------------------------
use "$raw_data/data_20240523_lease.dta", clear
keep if !missing(execution_month, execution_year)
drop id_Lease

gen half = ceil(execution_month/6)
gen yh   = yh(execution_year, half)
format yh %th

keep if yh < yh(2020,1)
collapse (mean) effectiverent2212usdperyear [fw=transactionsqft], by(city state)

rename city  hqcity
rename state hqstate

sort hqcity hqstate

tempfile _lease
save     "`_lease'", replace

use "`snapshot_clean'", clear
merge m:1 hqcity hqstate using "`_lease'"
drop if _merge==2   // drop lease-only rows
rename effectiverent2212usdperyear rent


*----------------------------------------------------------
* 1.6  Modal roles & wages  (keep _merge==1|3)
*----------------------------------------------------------
merge m:1 companyname using "$processed_data/modal_role_per_firm.dta", keep(1 3) nogen
merge m:1 user_id      using "$processed_data/worker_baseline_role",   keep(1 3) nogen
merge m:1 companyname using "$processed_data/wages_firm.dta",          keep(1 3) nogen


****************************************************************************
* 1.7  Variable construction (unchanged)
****************************************************************************

gen age     = 2020 - founded
label var age "Firm age as of 2020"
encode companyname, gen(firm_id)
encode msa,        gen(msa_id)

gen startup = age <= 10
gen covid   = yh >= 120    // 120 = 2020H1
gen remote  = flexibility_score2

rename restrictedcontributionscount restricted_contributions
rename totalcontribution            total_contributions

sort user_id yh

* pre-COVID restricted contributions -------------------------------------*
gen pre_covid = yh < 120
by user_id: egen pre_covid_rest = total(cond(pre_covid & !missing(restricted_contributions), ///
                                             restricted_contributions, 0))

* interaction terms ------------------------------------------------------*
gen var3 = remote*covid
gen var4 = covid*startup
gen var5 = remote*covid*startup
gen var6 = covid*company_teleworkable
gen var7 = startup*covid*company_teleworkable


tempfile _master_panel
save     "`_master_panel'", replace

****************************************************************************
* 2.  Parameterised sample creation
****************************************************************************

local sample_types "unbalanced balanced precovid balanced_pre"

foreach sample of local sample_types {

    use "`_master_panel'", clear

    /* ----------------------- variant-specific filters ---------------- */
    if "`sample'" == "balanced" {
        gsort user_id yh
        quietly summarize yh, meanonly
        local global_min = r(min)
        local global_max = r(max)

        by user_id: egen min_time = min(yh)
        by user_id: egen max_time = max(yh)
        by user_id: egen nobs     = count(yh)

        preserve
            contract yh, freq(count_yh)
            local total_periods = _N
        restore

        keep if min_time==`global_min' & max_time==`global_max' & nobs==`total_periods'
        drop min_time max_time nobs
    }

    if "`sample'" == "precovid" {
        keep if pre_covid_rest > 0
    }
	
	if "`sample'" == "balanced_pre" {
		keep if pre_covid_rest > 0
		
        gsort user_id yh
        quietly summarize yh, meanonly
        local global_min = r(min)
        local global_max = r(max)

        by user_id: egen min_time = min(yh)
        by user_id: egen max_time = max(yh)
        by user_id: egen nobs     = count(yh)

        preserve
            contract yh, freq(count_yh)
            local total_periods = _N
        restore

        keep if min_time==`global_min' & max_time==`global_max' & nobs==`total_periods'
        drop min_time max_time nobs
		
    }
	
	* outcome transforms -----------------------------------------------------*
	local original_outcomes "total_contributions restricted_contributions"
	foreach var of local original_outcomes {
		winsor2 `var', cuts(5 95) suffix(_we)
		bysort yh: egen `var'_q100 = xtile(`var'), nq(100)
		label var `var'_we    "`var' (Winsorised [5–95])"
		label var `var'_q100 "`var' (Percentile rank [1–100])"
	}
	
	* common-sample screen ----------------------------------------------------*
	local keep_vars ///
		user_id firm_id yh covid remote startup company_teleworkable ///
		total_contributions_q100 restricted_contributions_q100 ///
		var3 var4 var5 var6 var7

	egen miss_ct = rowmiss(`keep_vars')
	keep if miss_ct==0

    /* ----------------------- output ---------------------------------- */
    local base   = "$processed_data/user_panel_`sample'"
    quietly save   "`base'.dta", replace
    export delimited "../data/samples/user_panel_`sample'.csv", replace

    * progress message ---------------------------------------------------
    di as txt "✓ Created `sample' sample (" _N " obs)"
}

****************************************************************************
* 3.  Done
****************************************************************************
log close
exit, clear
