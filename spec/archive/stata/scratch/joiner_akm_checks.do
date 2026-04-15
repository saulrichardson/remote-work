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
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/joiner_akm_checks.log", replace text




*==========================================================================*
* joiner_akm_checks.do
*--------------------------------------------------------------------------*
* Diagnose remote versus on-site hiring patterns for first-time joiners
* using person- and firm-level AKM fixed effects.
*
* Run from repository root:
*     do spec/joiner_akm_checks.do
*==========================================================================*

version 17.0
set more off

do "../globals.do"

local joiner_file  "$processed_data/joiner_akm_panel.dta"
local results_dir  "$results/akm_joiner_checks"

confirm file "`joiner_file'"
cap mkdir "`results_dir'"

use "`joiner_file'", clear

keep firm_id yh year akm_pfe_norm_2013to19 user_id ///
     remote covid startup company_teleworkable var3 var4 var5 var6 var7

drop if missing(akm_pfe_norm_2013to19)

quietly summarize akm_pfe_norm_2013to19 if year < 2020, detail
scalar akm_cut = r(p50)

gen byte high_joiner = akm_pfe_norm_2013to19 >= akm_cut if !missing(akm_pfe_norm_2013to19)
drop if missing(high_joiner)

foreach v in remote covid startup company_teleworkable var3 var4 var5 var6 var7 {
    drop if missing(`v')
}

collapse (mean) share_high = high_joiner ///
         (mean) mean_akm   = akm_pfe_norm_2013to19 ///
         (count) joiners   = user_id ///
         (firstnm) remote  = remote ///
         (firstnm) covid   = covid ///
         (firstnm) startup = startup ///
         (firstnm) company_teleworkable = company_teleworkable ///
         (firstnm) var3 = var3 ///
         (firstnm) var4 = var4 ///
         (firstnm) var5 = var5 ///
         (firstnm) var6 = var6 ///
         (firstnm) var7 = var7, by(firm_id yh)

gen byte post = covid

encode firm_id, gen(firm_id_id)
drop firm_id
rename firm_id_id firm_id

save "`results_dir'/joiner_selection_panel.dta", replace
export delimited using "`results_dir'/joiner_selection_panel.csv", replace

reghdfe share_high var3 var5 var4 [aw = joiners], absorb(firm_id yh) vce(cluster firm_id)
reghdfe mean_akm  var3 var5 var4 [aw = joiners], absorb(firm_id yh) vce(cluster firm_id)

ivreghdfe share_high (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)
ivreghdfe mean_akm  (var3 var5 = var6 var7) var4, absorb(firm_id yh) vce(cluster firm_id)

log close
