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
# In earlier versions the *pre-COVID* ("precovid") sample was silently
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
do "../../spec/stata/_bootstrap.do"

****************************************************************************
* 1.  Build the *full* (unfiltered) master panel
****************************************************************************

*----------------------------------------------------------
* 1.1  User-level contributions (historic)
*----------------------------------------------------------
use "$processed_data/Contributions_Scoop.dta", clear

* drop inactive accounts --------------------------------------------------
gsort user_id year month
destring year month, replace


* derive half-year id ------------------------------------------------------
gen half = ceil(month/6)
gen yh   = yh(year, half)
format yh %th

* monthly → half-year collapse -------------------------------------------*
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

label var totalcontribution            "Total Contributions"
label var restrictedcontributionscount "Pvt Contributions"

tempfile user_yh_new
save     "`user_yh_new'", replace

* attach company names -----------------------------------------------------
// use "$processed_data/expanded_half_years_2.dta", clear
// keep if yh == yh(2022,1)
// keep user_id companyname yh

// duplicates tag user_id yh, gen(dup_tag)
// keep if dup_tag==0

// merge 1:1 user_id yh using "`user_yh_new'", keep(3) nogen

append using "`user_yh'"
save   "`user_yh'", replace

keep user_id year month

export delimited "~/Downloads/all_contributions.csv", replace



contributions_scoop file 
