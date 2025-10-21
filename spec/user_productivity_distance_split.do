*-----------------------------------------------------------------------
* heterogeneity_distance_base.do   —  IV and OLS split by distance bucket
*   base controls:  var3  var4
*   Outputs:
*     - IV  stats -> var5_distance_base.csv (existing filename retained)
*     - OLS stats -> var5_distance_base_ols.csv (new parallel output)
*-----------------------------------------------------------------------
* ---------------------------------------------------------------------
*  User-configurable parameters
* ---------------------------------------------------------------------
local nbins 3                      // default bins (3 = terciles)

* Allow optional override: second arg sets nbins (e.g., do ... precovid 2)
args panel_variant nbins_arg
if "`panel_variant'"=="" local panel_variant "precovid"
if "`nbins_arg'"!="" local nbins `nbins_arg'

use "$processed_data/user_panel_`panel_variant'.dta", clear

* 1.  Build firm-level distance terciles ---------------------------------
preserve
    keep firm_id avgdist_km
    duplicates drop firm_id, force          // one row per firm
    xtile gdist_tile = avgdist_km, nq(`nbins')
    keep firm_id gdist_tile
    tempfile dist_tiles
    save `dist_tiles'
restore

merge m:1 firm_id using `dist_tiles', nogenerate

* 2.  Prepare logging & output ------------------------------------------
cap mkdir "log"
capture log close
log using "log/het_dist_base.log", replace text

local result_dir "$results/het_dist_base_`panel_variant'_`nbins'"
cap mkdir "`result_dir'"
di as text "[distance_do] panel_variant=`panel_variant' nbins=`nbins' -> `result_dir'"


*--------------------------------------------------------------
* Open postfile
*--------------------------------------------------------------
tempfile out
capture postclose handle
postfile handle ///
    str8   bucket       ///  1, 2, 3
    double coef3 se3 pval3   /// var3 stats
    double coef5 se5 pval5   /// var5 stats
    double rkf nobs          /// first‐stage F and N
    using `out', replace

*--------------------------------------------------------------
* Loop over buckets
*--------------------------------------------------------------
forvalues g = 1/`nbins' {

    di as text "=== Distance bucket `g' ==="

    ivreghdfe total_contributions_q100 ///
        (var3 var5 = var6 var7)  var4 ///
        if gdist_tile == `g', ///
        absorb(firm_id#user_id yh) vce(cluster user_id) savefirst

    // compute stats for var3
    local b3   = _b[var3]
    local se3  = _se[var3]
    local p3   = 2*ttail(e(df_r), abs(`b3'/`se3'))

    // compute stats for var5
    local b5   = _b[var5]
    local se5  = _se[var5]
    local p5   = 2*ttail(e(df_r), abs(`b5'/`se5'))

    post handle ("`g'") ///
        (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') ///
        (e(rkf)) (e(N))

}

postclose handle
preserve
use `out', clear
export delimited using "`result_dir'/var5_distance_base.csv", replace
restore
log close


*-----------------------------------------------------------------------
* 3.  OLS version (parallel output)
*-----------------------------------------------------------------------
cap mkdir "log"
capture log close
log using "log/het_dist_base.log", append text

tempfile out_ols
capture postclose handle_ols
postfile handle_ols ///
    str8   bucket       ///  1, 2, 3, ...
    double coef3 se3 pval3   /// var3 stats
    double coef5 se5 pval5   /// var5 stats
    double rkf nobs          /// placeholder for consistency; rkf missing for OLS
    using `out_ols', replace

forvalues g = 1/`nbins' {

    di as text "=== OLS: Distance bucket `g' ==="

    reghdfe total_contributions_q100 ///
        var3 var5  var4               ///
        if gdist_tile == `g',         ///
        absorb(firm_id#user_id yh) vce(cluster user_id)

    // compute stats for var3
    local b3   = _b[var3]
    local se3  = _se[var3]
    local p3   = 2*ttail(e(df_r), abs(`b3'/`se3'))

    // compute stats for var5
    local b5   = _b[var5]
    local se5  = _se[var5]
    local p5   = 2*ttail(e(df_r), abs(`b5'/`se5'))

    post handle_ols ("`g'") ///
        (`b3') (`se3') (`p3') ///
        (`b5') (`se5') (`p5') ///
        (.) (e(N))
}

postclose handle_ols
preserve
use `out_ols', clear
export delimited using "`result_dir'/var5_distance_base_ols.csv", replace
restore

log close
