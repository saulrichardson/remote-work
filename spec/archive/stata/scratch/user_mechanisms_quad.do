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
*  spec/user_mechanisms_quad.do
*  ------------------------------------------------------------------
*  Unified script to estimate, for multiple mechanisms M,
*    - Remote × Post (var3)
*    - Remote × Post × Startup (var5)
*    - Remote × Post × M (var3_M)
*    - Remote × Post × Startup × M (var5_M)
*  with OLS and IV (worker–firm FE; cluster user), without covid×M terms.
*
*  Mechanisms included:
*    - tile_rent (above-median rent)
*    - tile_hhi (above-median HHI from firm_panel)
*    - seniority_4 (binary L4+)
*    - vacancy_per_size (continuous) and hi_vac_size (above-median)
*
*  Instruments for endogenous: var3, var5, var3_M, var5_M
*    - var6, var7, var6_M, var7_M
*
*  Outputs: results/raw/user_mechanisms_quad_<panel>/consolidated_results.csv
*
*  Usage:
*      do spec/user_mechanisms_quad.do            // default panel = precovid
*      do spec/user_mechanisms_quad.do balanced   // or: unbalanced | balanced_pre
*====================================================================*

 log close _all

//--------------------------------------------------------------------*
* 0. Parse optional panel variant argument                            *
//--------------------------------------------------------------------*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

//--------------------------------------------------------------------*
* 1. Globals & open main panel                                        *
//--------------------------------------------------------------------*

do "../globals.do"

local SPECNAME  "user_mechanisms_quad_`panel_variant'"
local OUTDIR    "$results/`SPECNAME'"
cap mkdir "`OUTDIR'"
log using "`OUTDIR'/run.log", replace text

use "$processed_data/user_panel_`panel_variant'.dta", clear

// Consistent lowercase firm key
gen companyname_c = lower(companyname)

// Seniority flag (L4+ as in existing scripts)
//  confirm variable seniority_levels
// if !_rc {
//     gen byte seniority_4 = !inrange(seniority_levels,1,3)
// }

gen byte tile_seniority = !inrange(seniority_levels,1,3)
//--------------------------------------------------------------------*
* 2. Merge firm-level rent & HHI tiles from firm_panel (match logic)  *
//--------------------------------------------------------------------*

preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup employeecount
    gen companyname_c = lower(companyname)
    // Collapse to last during Covid per company (replicates prior logic)
    collapse (last) startup (last) rent (last) hhi_1000 (last) employeecount ///
        if covid, by(companyname_c)
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi = hhi_1000, nq(2)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(1 3) nogen








// Separate results file for mechanism-tests style (Post×M and Post×Startup×M)
tempfile out_mech
 postclose handle_mech
postfile handle_mech ///
    str6  model_type ///
    str24 mechanism  ///
    str20 variant    ///
    str16 param      ///
    double coef se pval ///
    double rkf ///
    long   nobs ///
    using `out_mech', replace


for var in tile_hhi tile_rent tile_seniority {
	
	local M var
    // Build interactions
    gen double var3_M = var3*`M'
	gen double var4_M = var4*`M'
    gen double var5_M = var5*`M'
    gen double var6_M = var6*`M'
    gen double var7_M = var7*`M'

    // OLS
     reghdfe total_contributions_q100 var3 var5 var3_M var5_M var4 var4_M///
        if !missing(`M'), absorb(firm_id#user_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 var3_M var5_M {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`Mlab'") ("`Mvar'") ("`p'") ///
            (`b') (`se') (`pval') (.) (`N')
    }

    // IV
     noisily ivreghdfe total_contributions_q100 ///
        (var3 var5 var3_M var5_M = var6 var7 var6_M var7_M) var4 var4_M///
        var4 if !missing(`M'), absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
    if _rc == 0 {
        local rkf = e(rkf)
        local N   = e(N)
        foreach p in var3 var5 var3_M var5_M {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("IV") ("`Mlab'") ("`Mvar'") ("`p'") ///
                (`b') (`se') (`pval') (`rkf') (`N')
        }
    }

    // Clean up interactions
    drop var3_M var5_M var6_M var7_M var4_M

}



//--------------------------------------------------------------------*
* 8. Export results                                                   *
//--------------------------------------------------------------------*

postclose handle
use `out', clear

export delimited using "`OUTDIR'/consolidated_results.csv", ///
    replace delimiter(",") quote

di as result "→ CSV written: `OUTDIR'/consolidated_results.csv"

// Export mechanism-tests style
postclose handle_mech
use `out_mech', clear
export delimited using "`OUTDIR'/consolidated_results_mechstyle.csv", ///
    replace delimiter(",") quote
di as result "→ CSV written: `OUTDIR'/consolidated_results_mechstyle.csv"
log close
