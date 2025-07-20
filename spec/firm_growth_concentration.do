// -----------------------------------------------------------------------------
// firm_growth_concentration.do
// -----------------------------------------------------------------------------
// Specification that replaces labour-market tightness with Lightcast-based
// concentration (HHI) measures.
// -----------------------------------------------------------------------------

do "../src/globals.do"   // load path globals

capture log close
cap mkdir "log"
log using "log/firm_growth_concentration.log", replace text

// 1. Load baseline firm panel ------------------------------------------

use "$processed_data/firm_panel.dta", clear
// use "$processed_data/user_panel_precovid.dta", clear

gen companyname_c = lower(companyname)

preserve
// 2. Merge firm-level concentration measures ---------------------------



import delimited "$processed_data/firm_hq_concentration.csv", ///
    clear stringcols(_all)
rename companyname companyname_c

tempfile hhi
save `hhi'

restore

merge m:1 companyname_c using `hhi', keep(1 3) nogen

destring hhi_hq_fw_lg hhi_hq_hq_lg hhi_hq_eq_lg hhi_fwavg_lg, replace 

// 3. Build interaction variables ---------------------------------------

// Baseline index: hhi_hq_fw (HQ metro, firm-wide weights)

local v hhi_fwavg_lg
gen var3_hhi = var3 * hhi_fwavg_lg
gen var5_hhi = var5 * hhi_fwavg_lg
gen var6_hhi = var6 * hhi_fwavg_lg
gen var7_hhi = var7 * hhi_fwavg_lg



// 5. Baseline IV regression -------------------------------------------

ivreghdfe growth_rate_we ///
    (var3 var5 = var6 var7) ///
    var4, absorb(firm_id yh) vce(cluster firm_id)

// 6. Robustness: footprint-weighted HHI -------------------------------

ivreghdfe growth_rate_we ///
    (var3 var5 var3_hhi var5_hhi = var6 var7 var6_hhi var7_hhi) ///
    var4, absorb(firm_id yh) vce(cluster firm_id)

log close

