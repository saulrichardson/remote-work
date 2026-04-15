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
log using "$LOG_DIR/user_productivity_akm_2.log", replace text




clear

do "../globals.do"

local data_file   "$processed_data/user_panel_precovid_akm.dta"
local results_dir "../results/raw/akm_user_productivity"
cap mkdir "`results_dir'"

noi di as text "→ Loading data: `data_file'"
use "`data_file'", clear

capture confirm variable in_core_multi
if _rc {
    di as error "ERROR: in_core_multi not found in `data_file'."
    di as error "       Re-build the user panel after generating core MSAs."
    exit 459
}

bys user_id (year start): gen byte last_spell = (_n == _N)

capture drop _merge

    preserve
        keep if last_spell
        keep user_id user_latitude user_longitude company_lat company_lon
        geodist user_latitude user_longitude company_lat company_lon, gen(dist_last_msa_km)
        keep user_id dist_last_msa_km
        tempfile lastdist
        save `lastdist'
    restore

merge m:1 user_id using `lastdist'
drop if _merge == 2
	
bys user_id: egen rank_pre  = mean(cond(year < 2020, total_contributions_q100, .))
bys user_id: egen rank_post = mean(cond(year >= 2020, total_contributions_q100, .))
gen contrib_rank_change = rank_post - rank_pre

drop if missing(akm_pfe_norm_2020to22, akm_pfe_norm_2016to19)

gen akm_change_2022 = akm_pfe_norm_2020to22 - akm_pfe_norm_2016to19

keep if last_spell

replace in_core_multi = 0 if missing(in_core_multi)

reghdfe akm_change_2022 covid, absorb(firm_id) vce(cluster user_id)
reghdfe akm_change_2022 in_core_multi, absorb(firm_id) vce(cluster user_id)
reghdfe contrib_rank_change in_core_multi, absorb(firm_id) vce(cluster user_id)
