*-----------------------------------------------------------------------
* heterogeneity_distance_base.do   —  IV split by distance tercile
*   base controls:  var3  var4
*-----------------------------------------------------------------------
* ---------------------------------------------------------------------
*  User-configurable parameters
* ---------------------------------------------------------------------
local nbins 3                      // ← change this single value to 2, etc.

args panel_variant
if "`panel_variant'"=="" local panel_variant "precovid"

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
use `out', clear
export delimited using "`result_dir'/var5_distance_base.csv", replace
log close
