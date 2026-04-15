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
log using "$LOG_DIR/merge_user_panel_with_akm.log", replace text




varabbrev*==========================================================================*
* merge_user_panel_with_akm.do
*--------------------------------------------------------------------------*
* Merge AKM person- and firm-level fixed effects (2013-19, 2016-19, 2020-22) into
* the canonical user panel. Run from repo root:
*     do spec/merge_user_panel_with_akm.do
*==========================================================================*

version 17.0
set more off

do "../globals.do"

local akm_dir "../../New/Data/AKM"
local akm_windows "2013to19 2016to19 2020to22"
local processed "$processed_data"

* 1. Load base user panel
noi di as text "→ Loading user panel"
use "`processed'/user_panel_precovid.dta", clear

tempfile user_base
save `user_base'

* 2. Person-level AKM (2013-19, 2016-19, 2020-22)
foreach window of local akm_windows {
    noi di as text "→ Importing person AKM (`window')"
    import delimited using "`akm_dir'/AKM_Estimate_PFE_`window'.csv", ///
        varnames(1) encoding(UTF-8) case(lower) clear
    rename rawpfe_pct        akm_pfe_raw_`window'
    rename normalizedpfe_pct akm_pfe_norm_`window'
    keep user_id akm_pfe_raw_`window' akm_pfe_norm_`window'
    destring user_id akm_pfe_raw_`window' akm_pfe_norm_`window', replace
    drop if missing(user_id)
    duplicates drop user_id, force
    tempfile pfe`window'
    save `pfe`window''
}

use `user_base', clear
merge m:1 user_id using `pfe2013to19', keep(master match) nogen
merge m:1 user_id using `pfe2016to19', keep(master match) nogen
merge m:1 user_id using `pfe2020to22', keep(master match) nogen

tempfile user_with_pfe
save `user_with_pfe'

* 3. Firm-level mapping pieces
noi di as text "→ Importing firm panel map"
use "`processed'/firm_panel.dta", clear
keep firm_id companyname
duplicates drop
replace companyname = lower(strtrim(companyname))
rename companyname companyname_c
keep firm_id companyname_c

tempfile firm_map
save `firm_map'

noi di as text "→ Importing Scoop LinkedIn map"
import delimited using "`akm_dir'/Scoop_final.csv", varnames(1) encoding(UTF-8) case(lower) clear
keep companyname companyurl
duplicates drop
replace companyname = lower(strtrim(companyname))
replace companyurl  = lower(strtrim(companyurl))
keep if strpos(companyurl, "linkedin.com")

gen akm_linkedin_suffix = ""
replace akm_linkedin_suffix = regexs(1) if regexm(companyurl, "(company/[^/?#]+)")
keep if akm_linkedin_suffix != ""
rename companyname companyname_c
keep companyname_c akm_linkedin_suffix
duplicates drop companyname_c akm_linkedin_suffix, force

tempfile scoop_map
save `scoop_map'

* 4. Firm-level AKM for each window
foreach window of local akm_windows {
    noi di as text "→ Importing firm AKM (`window')"
    import delimited using "`akm_dir'/AKM_Estimate_FFE_`window'_WithAllPossibleURLs.csv", ///
        varnames(1) encoding(UTF-8) case(lower) clear
    rename rawffe_pct        akm_ffe_raw_`window'
    rename normalizedffe_pct akm_ffe_norm_`window'
    rename finalentityfactid akm_finalentity_id_`window'
    keep linkedin_url akm_ffe_raw_`window' akm_ffe_norm_`window' akm_finalentity_id_`window'
    replace linkedin_url = lower(strtrim(linkedin_url))
    rename linkedin_url akm_linkedin_suffix
    drop if missing(akm_linkedin_suffix)
    duplicates drop akm_linkedin_suffix, force

    merge m:1 akm_linkedin_suffix using `scoop_map', keep(match) nogen
    merge m:1 companyname_c      using `firm_map',  keep(match) nogen
    bysort firm_id akm_linkedin_suffix: keep if _n == 1
    keep firm_id akm_ffe_raw_`window' akm_ffe_norm_`window' akm_finalentity_id_`window'
    duplicates drop firm_id, force

    tempfile ffe`window'
    save `ffe`window''
}

* 5. Merge firm AKM
use `user_with_pfe', clear
merge m:1 firm_id using `ffe2013to19', keep(master match) nogen
merge m:1 firm_id using `ffe2016to19', keep(master match) nogen
merge m:1 firm_id using `ffe2020to22', keep(master match) nogen

foreach window of local akm_windows {
    quietly count if !missing(akm_ffe_raw_`window')
    noi di as text "   Firm FE matches (`window'): " as result r(N)
}

foreach window of local akm_windows {
    if "`window'" != "2020to22" {
        gen double akm_pfe_norm_pre_`window' = akm_pfe_norm_`window' if year < 2020
        bysort firm_id: egen double akm_pfe_pre_mean_`window' = mean(akm_pfe_norm_pre_`window')
        drop akm_pfe_norm_pre_`window'
    }
}

label var akm_pfe_raw_2013to19  "AKM worker FE (raw, 2013-19)"
label var akm_pfe_norm_2013to19 "AKM worker FE (normalized, 2013-19)"
label var akm_pfe_raw_2016to19  "AKM worker FE (raw, 2016-19)"
label var akm_pfe_norm_2016to19 "AKM worker FE (normalized, 2016-19)"
label var akm_ffe_raw_2013to19  "AKM firm FE (raw, 2013-19)"
label var akm_ffe_norm_2013to19 "AKM firm FE (normalized, 2013-19)"
label var akm_ffe_raw_2016to19  "AKM firm FE (raw, 2016-19)"
label var akm_ffe_norm_2016to19 "AKM firm FE (normalized, 2016-19)"
label var akm_finalentity_id_2013to19 "AKM FactSet entity id (2013-19)"
label var akm_finalentity_id_2016to19 "AKM FactSet entity id (2016-19)"
label var akm_pfe_pre_mean_2013to19 "Avg pre-2020 worker FE (2013-19)"
label var akm_pfe_pre_mean_2016to19 "Avg pre-2020 worker FE (2016-19)"
label var akm_pfe_raw_2020to22  "AKM worker FE (raw, 2020-22)"
label var akm_pfe_norm_2020to22 "AKM worker FE (normalized, 2020-22)"
label var akm_ffe_raw_2020to22  "AKM firm FE (raw, 2020-22)"
label var akm_ffe_norm_2020to22 "AKM firm FE (normalized, 2020-22)"
label var akm_finalentity_id_2020to22 "AKM FactSet entity id (2020-22)"

save "`processed'/user_panel_precovid_akm.dta", replace
noi di as text "→ Saved: `processed'/user_panel_precovid_akm.dta"

