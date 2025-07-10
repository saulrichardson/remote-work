********************************************************************************
*  build_firm_soc_panel_from_csv.do
*  Create company × SOC-4 × half-year panel for regressions
*  starting from firm_occ_panel_enriched.csv (produced by the Python build).
********************************************************************************

// ---------------------------------------------------------------------------
// 0) Globals & log setup
// ---------------------------------------------------------------------------

do "../src/globals.do"

capture log close
cap mkdir "log"
log using "log/build_firm_soc_panel.log", replace text

// ---------------------------------------------------------------------------
// 1) Load occupation-level panel (CSV) -----------------------------------
// ---------------------------------------------------------------------------

import delimited "$processed_data/firm_occ_panel_enriched.csv", ///
        varnames(1) clear stringcols(_all)

// ---------------------------------------------------------------------------
// 2) Within-group time-series vars (firm × SOC) ---------------------------
// ---------------------------------------------------------------------------

encode companyname, gen(firm_id)    // numeric firm id for FE / clusters
encode soc4,        gen(soc_id)     // numeric SOC id

sort companyname soc4 yh
by companyname soc4: gen headcount_lag = headcount[_n-1]

gen growth_rate = (headcount / headcount_lag) - 1  if headcount_lag > 0
gen join_rate   = joins / headcount_lag            if headcount_lag > 0
gen leave_rate  = leaves / headcount_lag           if headcount_lag > 0

* Winsorise to 1–99 pct (same as winsor2 default)
winsor2 growth_rate join_rate leave_rate, cuts(1 99) suffix(_we)

// ---------------------------------------------------------------------------
// 3) Merge static firm attributes ----------------------------------------
// ---------------------------------------------------------------------------

merge m:1 companyname using "$processed_data/scoop_firm_tele_2.dta", keep(match master)
drop _merge

merge m:1 companyname using "$raw_data/Scoop_clean_public.dta", ///
      keepusing(flexibility_score2) keep(match master)
drop _merge
rename flexibility_score2 remote

merge m:1 companyname using "$raw_data/Scoop_founding.dta", ///
      keepusing(founded) keep(match master)
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

save "$processed_data/firm_soc_panel.dta", replace
export delimited "../data/samples/firm_soc_panel.csv", replace

log close
