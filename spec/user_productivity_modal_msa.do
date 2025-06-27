*----------------------------------------------------------------------
* heterogeneity_modal_base.do  — IV split by modal-MSA status
*   base controls:  var3  var4
*----------------------------------------------------------------------
* ---------------------------------------------------------------------
*  User-configurable parameters
* ---------------------------------------------------------------------
local nbins 3                      // number of distance buckets for naming

args panel_variant
if "`panel_variant'"=="" local panel_variant "precovid"

use "$processed_data/user_panel_`panel_variant'.dta", clear

*----------------------------------------------------------------------
* 0.  Build 0 / 1 / 2 bucket  (run once if not already in the panel)
*----------------------------------------------------------------------
capture confirm var modal_cat
if _rc {
    generate byte in_modal_msa = (cbsacode == company_cbsacode) ///
          if !missing(cbsacode, company_cbsacode)

    generate byte modal_cat = .
    replace  modal_cat = 1 if in_modal_msa == 1
    replace  modal_cat = 0 if in_modal_msa == 0
    replace  modal_cat = 2 if missing(in_modal_msa)
}

*----------------------------------------------------------------------
* 1.  Logging & output setup
*----------------------------------------------------------------------
cap mkdir "log"
capture log close
log using "log/het_modal_base.log", replace text

local result_dir "$results/het_modal_base_`panel_variant'_`nbins'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str8   bucket       ///  1, 2, 3
    double coef3 se3 pval3   /// var3 stats
    double coef5 se5 pval5   /// var5 stats
    double rkf nobs          /// first‐stage F and N
    using `out', replace


*----------------------------------------------------------------------
* 2.  Loop over the three modal buckets
*----------------------------------------------------------------------
foreach g in 0 1 2 {

    di as text "=== modal_cat `g'  (0=out,1=in,2=unk) ==="

    ivreghdfe total_contributions_q100                       ///
        (var3 var5 = var6 var7)  var4                       ///
        if modal_cat == `g',                                ///
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
export delimited using "`result_dir'/var5_modal_base.csv", replace

log close
