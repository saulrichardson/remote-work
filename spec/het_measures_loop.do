*---------------------------------------------------------------------
* spec/het_measures_loop.do
*   Ultra-light heterogeneity harness – modelled after the tightness
*   script.  It:
*       1) loads the chosen user panel (balanced / precovid / …),
*       2) merges any additional firm-level measures you care about
*          (vacancy, HHI, tightness, rent, …),
*       3) loops over a *single* local macro that lists the measures
*          you wish to test and – for each –
*             • builds a high-dummy (> median),
*             • creates the corresponding interaction terms,
*             • runs the baseline IV regression.
*   Nothing is written to disk – all results are shown in the log.  If
*   you want to capture them, wrap the regression call in the usual
*   postfile / post / postclose pattern.
*---------------------------------------------------------------------

//--------------------------------------------------------------------
// 0.  Choose panel variant (precovid / balanced / …)
//--------------------------------------------------------------------
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

//--------------------------------------------------------------------
// 1.  Load base panel
//--------------------------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

//--------------------------------------------------------------------
// 2.  Merge extra firm-level measures
//     ‑-- Add or remove merge lines as needed.  Keep(match) ensures we
//        only retain rows present in *both* datasets.
//--------------------------------------------------------------------

// Vacancy measure (CSV with firm-level vacancy_rate)
capture merge m:1 companyname using "$processed_data/vacancy_measures_2020.csv", keep(match) nogen

// ─── All other firm-level heterogeneity data (HHI, tightness, rent …)
//     have been removed for this trimmed version. If you need additional
//     measures later, simply add further `merge` lines here and list the
//     corresponding variable names in the macro below.

//--------------------------------------------------------------------
// 3.  Treatment variables
//     The baseline interactions (var3–var7, var4) are *already present*
//     in the loaded panel.  We therefore skip their re-creation and only
//     check that they exist.  If any are missing, we abort with a clear
//     error message so the user knows the input panel is incomplete.
//--------------------------------------------------------------------

foreach v in var3 var4 var5 var6 var7 {
    capture confirm variable `v'
    if _rc {
        di as error "Required variable `v' is missing from the panel."
        error 498
    }
}

//--------------------------------------------------------------------
// 4.  List the *firm-level* measures to test
//--------------------------------------------------------------------
local measures vacancy_rate

//--------------------------------------------------------------------
// 5.  Loop – one regression per measure
//--------------------------------------------------------------------

foreach m of local measures {

    di as text "-------------------------------------------------------"
    di as text "Running IV with heterogeneity: `m'"
    di as text "-------------------------------------------------------"

    // 5a.  High-dummy (> median)
    quietly summarize `m', detail
    scalar med_`m' = r(p50)
    gen byte hi_`m' = (`m' > med_`m') if !missing(`m')

    // 5b.  Interaction terms that depend on the measure
    gen var3_`m' = covid * remote                 * hi_`m'
    gen var5_`m' = covid * startup * remote       * hi_`m'
    gen var6_`m' = covid * teleworkable           * hi_`m'
    gen var7_`m' = covid * startup * teleworkable * hi_`m'

    // 5c.  IV regression
    ivreghdfe total_contributions_q100                           ///
        (var3 var5 var3_`m' var5_`m' =                          ///
         var6 var7 var6_`m' var7_`m')                           ///
        var4,                                                   ///
        absorb(firm_id#user_id yh) vce(cluster user_id)

    // Clean-up before next iteration
    drop hi_`m' var3_`m' var5_`m' var6_`m' var7_`m'
}

di as result "✓ All heterogeneity regressions completed."
