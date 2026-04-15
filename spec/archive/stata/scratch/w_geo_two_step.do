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
*  w_geo_two_step.do
*  — Professor-style two-step geography factor + equivalence check
*====================================================================*

clear all
set more off

*--------------------------------------------------------------------*
* Argument parsing
*--------------------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

*--------------------------------------------------------------------*
* Dependency checks and paths
*--------------------------------------------------------------------*
capture which reghdfe
if _rc {
    di as error "reghdfe package is required but not installed."
    exit 459
}

local data_path "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
local results_path "/Users/saul/Dropbox/Remote Work Startups/main/results/raw"

capture confirm file "`data_path'/user_panel_`panel_variant'.dta"
if _rc {
    di as error "Expected file `data_path'/user_panel_`panel_variant'.dta not found."
    exit 601
}

global processed_data "`data_path'"
global results "`results_path'"

*--------------------------------------------------------------------*
* 1) Load original panel and verify variables
*--------------------------------------------------------------------*
use "`data_path'/user_panel_`panel_variant'.dta", clear

foreach reqvar in salary msa companyname title yh {
    capture confirm variable `reqvar'
    if _rc {
        di as error "Required variable `reqvar' is missing from the panel."
        exit 460
    }
}

capture confirm numeric variable salary
if _rc {
    destring salary, replace
    capture confirm numeric variable salary
    if _rc {
        di as error "Variable salary could not be converted to numeric."
        exit 461
    }
}

assert !missing(salary)
assert salary > 0

gen double lwage = ln(salary)
label var lwage "Log wage (constructed from salary)"

*--------------------------------------------------------------------*
* 2) Encode identifiers required for FEs
*--------------------------------------------------------------------*
capture confirm numeric variable firm_id
if _rc {
    encode companyname, gen(firm_id)
    capture confirm numeric variable firm_id
    if _rc {
        di as error "Failed to encode firm identifiers."
        exit 462
    }
}

capture confirm numeric variable title_id
if _rc {
    encode title, gen(title_id)
    capture confirm numeric variable title_id
    if _rc {
        di as error "Failed to encode title identifiers."
        exit 463
    }
}

capture confirm numeric variable msa_id
if _rc {
    encode msa, gen(msa_id)
    capture confirm numeric variable msa_id
    if _rc {
        di as error "Failed to encode MSA identifiers."
        exit 464
    }
}

gen int year_from_yh = year(dofh(yh))
gen byte half_from_yh = halfyear(dofh(yh))
assert !missing(year_from_yh)

*--------------------------------------------------------------------*
* 3) Two-step FWL procedure on pre-period (2018–2019)
*--------------------------------------------------------------------*
preserve
    keep if yh < yh(2020, 1)
    assert `c(N)' > 0

    count if missing(msa_id) | missing(firm_id) | missing(title_id) | missing(yh) | missing(lwage)
    if r(N) {
        di as error "`r(N)' pre-period observations lack identifiers required for FE estimation; dropping."
        drop if missing(msa_id) | missing(firm_id) | missing(title_id) | missing(yh) | missing(lwage)
    }

    assert !missing(msa_id, firm_id, title_id, yh, lwage)

    di as text "Pre-period observations retained (two-step): " %9.0f `c(N)'

    reghdfe lwage, absorb(firm_id title_id yh) residuals(resid_step1)

    summarize resid_step1

    reghdfe resid_step1, absorb(w_geo_pre_twostep=msa_id)

    summarize w_geo_pre_twostep, detail

    collapse (mean) w_geo_pre_twostep, by(msa msa_id)
    rename w_geo_pre_twostep w_geo_m_pre_twostep

    tempfile gmap_twostep
    save `gmap_twostep'
restore

*--------------------------------------------------------------------*
* 4) Merge two-step geography price back to full panel
*--------------------------------------------------------------------*
capture drop _merge
merge m:1 msa_id using `gmap_twostep'
count if _merge == 1
if r(N) {
    di as error "`r(N)' observations lack two-step geography mapping; dropping them."
    drop if _merge == 1
}

assert _merge == 3
drop _merge

count if missing(w_geo_m_pre_twostep)
if r(N) {
    di as error "`r(N)' observations have undefined two-step geography component; dropping them."
    drop if missing(w_geo_m_pre_twostep)
}

assert !missing(w_geo_m_pre_twostep)

gen double w_geo_hat_twostep = w_geo_m_pre_twostep
label var w_geo_hat_twostep "Geography-only log wage (two-step)"
rename w_geo_hat_twostep w_geo_hat
label var w_geo_hat "Geography-only log wage (two-step)"

*--------------------------------------------------------------------*
* 6) Save outputs
*--------------------------------------------------------------------*
local outpath "`data_path'/user_panel_w_geo_twostep_`panel_variant'.dta"
save "`outpath'", replace
di as result "Saved two-step geography panel to: `outpath'"

preserve
    keep msa msa_id w_geo_m_pre_twostep
    duplicates drop
    export delimited using "$results/w_geo_mapping_twostep_`panel_variant'.csv", replace
restore

di as result "Two-step workflow complete for variant: `panel_variant'"
