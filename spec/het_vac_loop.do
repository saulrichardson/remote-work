*---------------------------------------------------------------------
* spec/het_vac_loop.do
*   Heterogeneity harness for vacancy-based labour-market
*   concentration measures that are available at the firm level.
*
*   Steps (mirrors het_hhi_loop.do):
*     1) Loads the baseline firm or user panel
*     2) Merges vacancy_measures_2020.csv (vacancy, gap, and normalised
*        ratios)
*     3) Loops over the list of vacancy variables – for each one it
*          • builds the interaction terms (var3_vac … var7_vac),
*          • runs the IV regression with the extra interactions,
*          • cleans up before the next iteration.
*
*   Usage examples (from Stata command line):
*
*       do spec/het_vac_loop.do               // default firm panel
*       do spec/het_vac_loop.do user          // user panel instead
*
*---------------------------------------------------------------------

//--------------------------------------------------------------------
// 0. Choose panel (firm | user)
//--------------------------------------------------------------------
do "../src/globals.do"

// Open a log so we capture full output
capture log close _all
log using "$results/het_vac_loop.log", text replace

args panel
if "`panel'" == "" local panel "user"

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
// 2. Merge vacancy concentration measures
//--------------------------------------------------------------------

preserve

// Import vacancy measures
// Import vacancy measures produced by build_vacancy_measures.py
import delimited "$processed_data/vacancy_measures_2020.csv", clear stringcols(_all)
rename companyname companyname_c

tempfile _vac
save "`_vac'"

restore

gen companyname_c = lower(companyname)
merge m:1 companyname_c using "`_vac'", keep(1 3) nogen



// Ensure numeric types (import may yield strings)
// Ensure numeric types (import may yield strings) for the measures we use
destring vacancy gap vacancy_per_size vacancy_per_hire, replace force

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
// 4. Vacancy variables to loop over
//--------------------------------------------------------------------
// Vacancy variables (raw count, ratios, and gap) to test heterogeneity
local vac_vars vacancy vacancy_per_size vacancy_per_hire gap

//--------------------------------------------------------------------
// 5. Loop – run IV for each vacancy variant
//--------------------------------------------------------------------

foreach v of local vac_vars {



    // Skip if variable not present
    capture confirm variable `v'
    if _rc {
        di as txt "[skip] Vacancy variable `v' not found in data."
        continue
    }

    // Description for logging
    local desc ""
    if "`v'" == "vacancy"            local desc "Raw vacancy count"
    else if "`v'" == "vacancy_per_size"  local desc "Vacancies per 2019-H2 headcount"
    else if "`v'" == "vacancy_per_hire"  local desc "Vacancies per 2019-H2 hires"
    else if "`v'" == "gap"               local desc "Vacancy gap (vacancies vs hires)"

    di as text "-------------------------------------------------------"
    di as text "Running IV – vacancy variable: `v'  ( `desc' ) – continuous + dummy"
    di as text "-------------------------------------------------------"

    // ---------------- Continuous interaction ------------------------
    gen var3_`v' = var3 * `v'
    gen var5_`v' = var5 * `v'
    gen var6_`v' = var6 * `v'
    gen var7_`v' = var7 * `v'

    di as text "[1/2] Continuous interaction"
    ivreghdfe `DEPVAR' ///
        (var3 var5 var3_`v' var5_`v' = ///
         var6 var7 var6_`v' var7_`v') ///
        var4, absorb(`FE') vce(cluster `CLUSTER')

    drop var3_`v' var5_`v' var6_`v' var7_`v'

    // ---------------- High / Low dummy interaction ------------------
    quietly summarize `v', detail
    scalar med_`v' = r(p50)
    gen byte hi_`v' = (`v' > med_`v') if !missing(`v')

    di as text "[2/2] High (> median) dummy interaction – cut-off: " med_`v'

    gen var3_hi_`v' = var3 * hi_`v'
    gen var5_hi_`v' = var5 * hi_`v'
    gen var6_hi_`v' = var6 * hi_`v'
    gen var7_hi_`v' = var7 * hi_`v'

    ivreghdfe `DEPVAR' ///
        (var3 var5 var3_hi_`v' var5_hi_`v' = ///
         var6 var7 var6_hi_`v' var7_hi_`v') ///
        var4, absorb(`FE') vce(cluster `CLUSTER')

    drop hi_`v' var3_hi_`v' var5_hi_`v' var6_hi_`v' var7_hi_`v'
}

di as result "✓ Vacancy heterogeneity regressions completed."

log close
