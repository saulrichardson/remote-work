********************************************************************************
*  build_firm_soc_panel_from_csv.do
*  Create company × SOC-4 × half-year panel for regressions
*  starting from firm_occ_panel_enriched.csv (produced by the Python build).
********************************************************************************

// ---------------------------------------------------------------------------
// 0) Globals & log setup
// ---------------------------------------------------------------------------

do "globals.do"

capture log close
cap mkdir "log"
log using "log/build_firm_soc_panel.log", replace text

// ---------------------------------------------------------------------------
// 1) Load occupation-level panel (CSV) -----------------------------------
// ---------------------------------------------------------------------------

import delimited "$processed_data/firm_occ_panel_enriched.csv", ///
        varnames(1) clear stringcols(_all)
		

* Convert headcount, its lag, joins, and leaves to numeric (non-numeric chars → missing)
destring headcount joins leaves yh, replace force


* 1) recover calendar year and half‐flag
gen int  cy   = floor(yh/2)        // 4038→2019, 4039→2019, 4040→2020
gen byte half = mod(yh,2) + 1      // 0→1 (H1), 1→2 (H2)

* 2) build a native %th date
gen hdate = yh(cy, half)      // Stata's yh(year, half) function

* 3) format & swap in place
format hdate %th                   // displays "2019h1", "2019h2", …
drop cy half yh
rename hdate yh


** 1) make numeric IDs
encode companyname, gen(firm_id)
encode soc4,        gen(soc_id)

* 2) build one panel ID (no labels)
egen panel_id = group(firm_id soc_id)


* 3) declare your panel
xtset panel_id yh

* 4) you can now use time‐series lags
gen headcount_lag = L.headcount


gen growth_rate = (headcount/headcount_lag) - 1   if headcount_lag < .
gen join_rate   = joins/ headcount_lag           if headcount_lag < .
gen leave_rate  = leaves/ headcount_lag           if headcount_lag < .
* 6) winsorise your rates at the 1st and 99th percentiles
winsor2 growth_rate join_rate leave_rate, cuts(1 99) suffix(_we)



*--------------------------------------------------------------*
*  1. Teleworkable scores                                      *
*--------------------------------------------------------------*
preserve
	use "$processed_data/scoop_firm_tele_2.dta", clear
	replace companyname = lower(companyname)
	tempfile teleclean
	save    `teleclean'
restore
merge m:1 companyname using `teleclean'
drop if _merge == 2
drop _merge

*--------------------------------------------------------------*
*  2. Remote-flexibility score                                 *
*--------------------------------------------------------------*
preserve
	use "$raw_data/Scoop_clean_public.dta", clear
	keep companyname flexibility_score2
	replace companyname = lower(companyname)
	tempfile flexclean
	save    `flexclean'
restore
merge m:1 companyname using `flexclean'
drop if _merge == 2
drop _merge
rename flexibility_score2 remote

*--------------------------------------------------------------*
*  3. Company founding year                                    *
*--------------------------------------------------------------*
preserve
	use "$raw_data/Scoop_founding.dta", clear
	keep companyname founded
	replace companyname = lower(companyname)
	tempfile foundclean
	save    `foundclean'
restore
merge m:1 companyname using `foundclean'
drop if _merge == 2
drop _merge


// ---------------------------------------------------------------------------
// 4) Derived dummies & interaction terms ---------------------------------
// ---------------------------------------------------------------------------

gen age     = 2020 - founded
gen startup = age <= 10

gen covid   = yh >= 120       // 2020-H1 == yh(2020,1) = 120

gen var3 = remote * covid
gen var4 = covid  * startup
gen var5 = remote * covid * startup
gen var6 = covid * teleworkable
gen var7 = startup * covid * teleworkable

// ---------------------------------------------------------------------------
// 5) Drop observations with missing core regressors ----------------------
// ---------------------------------------------------------------------------

local keep_vars ///
    firm_id soc4 yh covid remote startup teleworkable ///
    growth_rate_we join_rate_we leave_rate_we ///
    var3 var4 var5 var6 var7

egen miss_ct = rowmiss(`keep_vars')
gen byte complete = (miss_ct == 0)
count if complete == 0
di as error "Dropping " r(N) " incomplete row(s)."

keep if complete
drop miss_ct complete

// ---------------------------------------------------------------------------
// 6) Save panel -----------------------------------------------------------
// ---------------------------------------------------------------------------

sort companyname soc4 yh

save "$processed_data/firm_soc_panel.dta", replace
export delimited "../data/samples/firm_soc_panel.csv", replace

log close
