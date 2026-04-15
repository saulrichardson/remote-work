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
*  w_geo_experiment.do
*  — Extract geography-only wage component at the user level
*====================================================================*

clear all
set more off

*--------------------------------------------------------------------*
* Input argument: user panel flavour (default = precovid)
*--------------------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

*--------------------------------------------------------------------*
* 0) Dependencies and globals
*--------------------------------------------------------------------*
capture which reghdfe
if _rc {
    di as error "reghdfe package is required but not installed."
    exit 459
}

local repo_root = c(pwd)

* Ensure expected directory structure exists
capture confirm file "`repo_root'/data/processed/user_panel_`panel_variant'.dta"
if _rc {
    di as error "Expected file `repo_root'/data/processed/user_panel_`panel_variant'.dta not found."
    exit 601
}

global processed_data "`repo_root'/data/processed"
global results "`repo_root'/results/raw"

*--------------------------------------------------------------------*
* 1) Load user panel and validate required variables
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear

foreach reqvar in salary msa companyname title yh {
    capture confirm variable `reqvar'
    if _rc {
        di as error "Required variable `reqvar' is missing from the panel."
        exit 460
    }
}

di as text "Loaded panel variant: `panel_variant'"
di as text "Observations: `c(N)'"

quietly summarize yh
di as text "Half-year coverage:  " %th r(min) "  to  " %th r(max)

*--------------------------------------------------------------------*
* 2) Construct log wages (fail if salary not numeric/positive)
*--------------------------------------------------------------------*
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
* 3) Build identifiers required for FEs (fail if encoding impossible)
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

*--------------------------------------------------------------------*
* 4) Derive calendar year / half-year helpers
*--------------------------------------------------------------------*
gen int year_from_yh = year(dofh(yh))
gen byte half_from_yh = halfyear(dofh(yh))
assert !missing(year_from_yh) & inrange(year_from_yh, 1900, 2100)
label var year_from_yh "Calendar year (from yh)"
label var half_from_yh "Half-year indicator (1/2) from yh"

*--------------------------------------------------------------------*
* 5) Pre-period estimation: multi-way FE with geography component
*--------------------------------------------------------------------*
preserve
    keep if inrange(year_from_yh, 2018, 2019)
    assert `c(N)' > 0

    count if missing(msa_id) | missing(firm_id) | missing(title_id) | missing(yh) | missing(lwage)
    if r(N) {
        di as error "`r(N)' pre-period observations lack identifiers required for FE estimation."
        drop if missing(msa_id) | missing(firm_id) | missing(title_id) | missing(yh) | missing(lwage)
    }

    assert !missing(msa_id, firm_id, title_id, yh, lwage)

    di as text "Pre-period observations retained: " %9.0f `c(N)'
    tab year_from_yh half_from_yh

    reghdfe lwage, absorb(msa_fe_pre=msa_id firm_id title_id yh) vce(cluster firm_id)

    label var msa_fe_pre "MSA FE from pre-period wage regression"

    summarize msa_fe_pre, detail

    keep msa msa_id msa_fe_pre
    collapse (mean) msa_fe_pre, by(msa msa_id)
    rename msa_fe_pre w_geo_m_pre
    label var w_geo_m_pre "Frozen geo-only log wage component"

    tempfile gmap
    save `gmap'
restore

*--------------------------------------------------------------------*
* 6) Merge geography component back to full panel (require full match)
*--------------------------------------------------------------------*
capture drop _merge
merge m:1 msa_id using `gmap'
count if _merge == 1
if r(N) {
    di as error "`r(N)' observations lack pre-period MSA mapping; dropping them."
    drop if _merge == 1
}

assert _merge == 3
drop _merge

count if missing(w_geo_m_pre)
if r(N) {
    di as error "`r(N)' observations have undefined geography component (absent in pre-period estimation); dropping them."
    drop if missing(w_geo_m_pre)
}

assert !missing(w_geo_m_pre)

label var w_geo_m_pre "Geography-only log wage contribution (pre fit)"

gen double w_geo_hat = w_geo_m_pre
label var w_geo_hat "Estimated geography-only log wage (all periods)"

summarize w_geo_hat, detail
tab year_from_yh if !missing(w_geo_hat)

*--------------------------------------------------------------------*
* 7) Persist enriched panel for downstream analysis
*--------------------------------------------------------------------*
local outpath "$processed_data/user_panel_w_geo_`panel_variant'.dta"
save "`outpath'", replace
di as result "Saved enriched panel to: `outpath'"

*--------------------------------------------------------------------*
* 8) Export mapping for inspection
*--------------------------------------------------------------------*
preserve
    keep msa msa_id w_geo_m_pre
    duplicates drop
    export delimited using "$results/w_geo_mapping_`panel_variant'.csv", replace
restore

di as result "Finished geography-only wage extraction for variant: `panel_variant'"
