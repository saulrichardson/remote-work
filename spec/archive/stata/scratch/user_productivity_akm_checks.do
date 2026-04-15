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
log using "$LOG_DIR/user_productivity_akm_checks.log", replace text




*==========================================================================*
* user_productivity_akm_checks.do
*--------------------------------------------------------------------------*
* Runs three AKM-based diagnostics on the user panel.
*==========================================================================*
clear

do "../globals.do"

local data_file   "$processed_data/user_panel_precovid_akm.dta"
local results_dir "../results/raw/akm_user_productivity"
cap mkdir "`results_dir'"

noi di as text "→ Loading data: `data_file'"
use "`data_file'", clear

noi di as text "→ Constructing helper variables"
		

drop if missing(akm_pfe_norm_2013to19)
egen byte high_akm = xtile(akm_pfe_norm_2013to19), n(2)
egen byte firm_ffe_terc = xtile(akm_ffe_norm_2013to19), n(2)
egen byte firm_pre_terc = xtile(akm_pfe_pre_mean_2013to19), n(2)

egen byte person_pre_terc  = xtile(akm_pfe_norm_2013to19), n(2)

preserve
gen high_akm_proportion = high_akm == 2
collapse (mean) high_akm_proportion = high_akm_proportion, by(firm_id yh)

merge 1:1 firm_id yh using "$processed_data/firm_panel.dta"

reghdfe high_akm_proportion var3 var5 var4, absorb(firm_id yh) ///
      vce(cluster firm_id) 
ivreghdfe high_akm_proportion (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst		
		
restore

**************************************************************************
* Test 2: Proporition of High AKM
**************************************************************************

**************************************************************************
* Test 2: Heterogeneity by firm AKM FE deciles
**************************************************************************
noi di as text "→ Test 2: Firm AKM FE deciles"
forvalues g = 1/2 {
    noi di as text "Firm AKM FE decile `g'" 
    reghdfe total_contributions_q100 var3 var5 var4 if  person_pre_terc == `g', absorb(user_id firm_id yh) ///
        vce(cluster user_id) 
		
	ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 if  person_pre_terc == `g', ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
}

**************************************************************************
* Test 3: Heterogeneity by average pre-shock worker FE deciles
**************************************************************************
noi di as text "→ Test 3: Firm avg worker AKM deciles"
forvalues g = 1/2 {
	noi di as text "Firm avg worker AKM deciles `g'"
    reghdfe total_contributions_q100 var3 var5 var4 if firm_pre_terc == `g', absorb(user_id firm_id yh) ///
        vce(cluster user_id) 
		
	ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 if firm_pre_terc == `g', ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst
}

log close

