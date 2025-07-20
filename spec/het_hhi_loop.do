*---------------------------------------------------------------------
* spec/het_hhi_loop.do
*   Quick-start heterogeneity harness for **all** Lightcast labour-market
*   concentration (HHI) variants that are available at the firm level.
*
*   1) Loads the baseline firm or user panel
*   2) Merges firm_hq_concentration.csv (EIGHT HHI variables – four based
*      on the *largest-CZ → CBSA* mapping, four on the *fractional* mapping)
*   3) Loops over the list of HHI variables – for each one it
*        • builds the interaction terms (var3_hhi … var7_hhi),
*        • runs the IV regression with the extra interactions,
*        • cleans up before the next iteration.
*
*   Usage examples (from Stata command line):
*
*       do spec/het_hhi_loop.do               // uses default panel
*       do spec/het_hhi_loop.do user          // uses user panel instead
*
*---------------------------------------------------------------------

//--------------------------------------------------------------------
// 0. Choose panel (firm | user)
//--------------------------------------------------------------------
do "../src/globals.do"

//--------------------------------------------------------------------
// Open a log file so that we can inspect the full console output.
// The log is written to the generic $results directory defined in
// globals.do.  The file is overwritten each time the script runs so that
// users do not accumulate stale logs.
//--------------------------------------------------------------------

capture log close _all
log using "$results/het_hhi_loop.log", text replace

args panel
if "`panel'" == "" local panel "firm"

if "`panel'" == "firm" {
    local PANEL_FILE "$processed_data/firm_panel.dta"
    local FE "firm_id yh"        // FE for firm-level outcome
    local CLUSTER "firm_id"
    local DEPVAR "growth_rate_we"
}
else if "`panel'" == "user" {
    local PANEL_FILE "$processed_data/user_panel_precovid.dta"
    local FE "firm_id#user_id yh" // FE for user-level outcome
    local CLUSTER "user_id"
    local DEPVAR "total_contributions_q100"
}
else {
    di as error "Unknown panel type: `panel'. Use 'firm' or 'user'."
    exit 198
}

//--------------------------------------------------------------------
// 1. Load panel
//--------------------------------------------------------------------
use "`PANEL_FILE'", clear

//--------------------------------------------------------------------
// 2. Merge Lightcast concentration measures
//--------------------------------------------------------------------

// -------------------------------------------------------------------
// 2. Merge Lightcast concentration measures
//     – first run filefilter to strip Windows carriage-returns (\r)
//       from the CSV.  This guarantees that the column names we import
//       are clean and prevents the “variable\ invalid name” issue.
// -------------------------------------------------------------------

preserve

tempfile _csvclean
filefilter "$processed_data/firm_hq_concentration.csv" "`_csvclean'", from("\r") to("")

import delimited "`_csvclean'", clear stringcols(_all)
rename companyname companyname_c

tempfile _hhi
save `_hhi'

restore

gen companyname_c = lower(companyname)
merge m:1 companyname_c using `_hhi', keep(1 3) nogen

// -------------------------------------------------------------------
// 2b. Clean variable names – remove hidden control characters that may
//      arrive from the CSV header (carriage-return, line-feed, tab).
//      These invisible characters lead to mysterious “invalid name”
//      errors later on when the variable is referenced.
// -------------------------------------------------------------------

foreach v of varlist _all {
    local clean = "`v'"
    local clean = subinstr("`clean'", char(13), "", .)   // CR
    local clean = subinstr("`clean'", char(10), "", .)   // LF
    local clean = subinstr("`clean'", char(9),  "", .)   // TAB
    local clean = trim("`clean'")
    if "`clean'" != "`v'" rename `v' `clean'
}

// Ensure numeric types (import may yield strings)
// If new variants are added, include them here so they are coerced to numeric.
destring hhi_hq_fw_lg hhi_hq_hq_lg hhi_hq_eq_lg hhi_fwavg_lg hhi_hq_fw_fr hhi_hq_hq_fr hhi_hq_eq_fr hhi_fwavg_fr, replace force

//--------------------------------------------------------------------
// 3. Confirm baseline treatment variables exist
//--------------------------------------------------------------------
foreach v in var3 var4 var5 var6 var7 {
    capture confirm variable `v'
    if _rc {
        di as error "Required variable `v' is missing from the panel."
        exit 498
    }
}

//--------------------------------------------------------------------
// 4. HHI variables to loop over
//--------------------------------------------------------------------
// List of HHI variables to iterate over (kept on a single physical line to
// avoid CR/LF artefacts in names)
local hhi_vars hhi_hq_fw_lg hhi_hq_hq_lg hhi_hq_eq_lg hhi_fwavg_lg hhi_hq_fw_fr hhi_hq_hq_fr hhi_hq_eq_fr hhi_fwavg_fr

//--------------------------------------------------------------------
// 5. Loop – run IV for each HHI variant
//--------------------------------------------------------------------

foreach h of local hhi_vars {

    // ----------------------------------------------------------------
    // Some editors on Windows / macOS may leave an invisible carriage
    // return (char(13)) attached to tokens when the file uses CR-LF line
    // endings.  That hidden character turns, e.g., "hhi_hq_fw_lg" into
    // "hhi_hq_fw_lg\" which Stata rightly rejects as an invalid name.
    //
    // Strip char(13) defensively before using the token.
    // ----------------------------------------------------------------

    // Remove any carriage-return, line-feed, tab or leading/trailing spaces
    // that might have hitch-hiked into the token.
    local _clean = "`h'"
    local _clean = subinstr("`_clean'", char(13), "", .)  // CR
    local _clean = subinstr("`_clean'", char(10), "", .)  // LF
    local _clean = subinstr("`_clean'", char(9),  "", .)  // TAB
    local h = trim("`_clean'")


    // Skip if variable not present
    capture confirm variable `h'
    if _rc {
        di as txt "[skip] HHI variable `h' not found in data."
        continue
    }

    // ----------------------------------------------------------------
    // Pretty header so the log clearly states which spec is running
    // ----------------------------------------------------------------

    local desc ""
    if "`h'" == "hhi_hq_fw_lg"  local desc "HQ metro, firm-wide weights (largest-CZ mapping)"
    else if "`h'" == "hhi_hq_hq_lg"  local desc "HQ metro, HQ-only weights (largest-CZ mapping)"
    else if "`h'" == "hhi_hq_eq_lg"  local desc "HQ metro, equal weights (largest-CZ mapping)"
    else if "`h'" == "hhi_fwavg_lg"  local desc "Footprint-weighted average across metros (largest-CZ mapping)"
    else if "`h'" == "hhi_hq_fw_fr"  local desc "HQ metro, firm-wide weights (fractional mapping)"
    else if "`h'" == "hhi_hq_hq_fr"  local desc "HQ metro, HQ-only weights (fractional mapping)"
    else if "`h'" == "hhi_hq_eq_fr"  local desc "HQ metro, equal weights (fractional mapping)"
    else if "`h'" == "hhi_fwavg_fr"  local desc "Footprint-weighted average across metros (fractional mapping)"

    di as text "-------------------------------------------------------"
    di as text "Running IV – HHI variable: `h'  ( `desc' ) – continuous + dummy"
    di as text "-------------------------------------------------------"

    // ---------------- Continuous interaction ------------------------

    gen var3_`h' = var3 * `h'
    gen var5_`h' = var5 * `h'
    gen var6_`h' = var6 * `h'
    gen var7_`h' = var7 * `h'

    di as text "[1/2] Continuous interaction"

    // IV regression – continuous
    ivreghdfe `DEPVAR' ///
        (var3 var5 var3_`h' var5_`h' = ///
         var6 var7 var6_`h' var7_`h') ///
        var4, absorb(`FE') vce(cluster `CLUSTER')

    // Clean-up

    drop var3_`h' var5_`h' var6_`h' var7_`h'

    // ---------------- High / Low dummy interaction ------------------

    quietly summarize `h', detail
    scalar med_`h' = r(p50)
    gen byte hi_`h' = (`h' > med_`h') if !missing(`h')

    di as text "[2/2] High (> median) dummy interaction  – cut-off: " med_`h'

    gen var3_hi_`h' = var3 * hi_`h'
    gen var5_hi_`h' = var5 * hi_`h'
    gen var6_hi_`h' = var6 * hi_`h'
    gen var7_hi_`h' = var7 * hi_`h'

    ivreghdfe `DEPVAR' ///
        (var3 var5 var3_hi_`h' var5_hi_`h' = ///
         var6 var7 var6_hi_`h' var7_hi_`h') ///
        var4, absorb(`FE') vce(cluster `CLUSTER')

    // Clean-up dummy vars
    drop hi_`h' var3_hi_`h' var5_hi_`h' var6_hi_`h' var7_hi_`h'
}

di as result "✓ All HHI heterogeneity regressions completed."

// Close the log so that output is written to disk
log close
