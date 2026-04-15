********************************************************************************
* build_firm_horse_race_scores.do
*
* Purpose:
*   Construct firm-level "horse race" exposure measures from occupation-level
*   inputs:
*     (1) Offshorability  (task_offshorability by SOC)
*     (2) GenAI exposure  (genaiexp_estz_* by SOC)
*
* Approach (mirrors the teleworkability build logic):
*   - Map LinkedIn roles (role_k1000) to SOC codes using rolek1000_onet_cw.csv
*   - Merge SOC-level measures onto worker spells
*   - Restrict to pre-COVID spells (2018–2019 window, consistent with
*     build_firm_teleworkable_scores.do)
*   - Collapse to companyname means (employee-weighted via spell rows)
*
* Outputs:
*   - $processed_data/scoop_firm_horse_race.dta
*   - Optional CSV mirror in data/samples/
********************************************************************************

do "../../spec/stata/_bootstrap.do"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/build_firm_horse_race_scores.log", replace text


********************************************************************************
* 1) Role → SOC crosswalk (role_k1000_onet_cw.csv)
********************************************************************************

import delimited "$raw_data/rolek1000_onet_cw.csv", varnames(1)  ///
    clear bindquote(strict) stringcols(_all)

replace role_k1000 = strtrim(role_k1000)
replace onet_code  = strtrim(onet_code)

gen before_dot = substr(onet_code, 1, 7)  // e.g., "15-1130"
gen after_dot  = substr(onet_code, 8, .)  // e.g., ".00"
keep if after_dot == ".00"

rename before_dot soc_new
keep role_k1000 soc_new
drop if role_k1000 == "" | soc_new == ""
duplicates drop role_k1000, force

tempfile tf_role_soc
save `tf_role_soc', replace


********************************************************************************
* 2) GenAI exposure (SOC-level)
*    NOTE: The raw file often contains Excel date-corrupted SOC codes (e.g. "Nov-21").
*          We drop invalid SOC codes and fail if duplicates remain after cleaning.
********************************************************************************

import delimited "$raw_data/horse_race/Occ_GenAI_Exposure.csv", ///
    varnames(1) clear bindquote(strict) stringcols(_all)

rename soc2010 soc_new
replace soc_new = strtrim(soc_new)

gen byte soc_ok = regexm(soc_new, "^[0-9][0-9]-[0-9][0-9][0-9][0-9]$")
count if !soc_ok
di as error "GenAI: dropping " r(N) " row(s) with invalid SOC code formatting (likely Excel date corruption)."
keep if soc_ok
drop soc_ok

duplicates tag soc_new, gen(_dup)
count if _dup > 0
if r(N) > 0 {
    di as error "GenAI: SOC codes are duplicated after cleaning; refusing to proceed."
    di as error "Fix the raw file (preserve SOC as text) or provide a clean crosswalk."
    exit 459
}
drop _dup

destring genaiexp_estz_total genaiexp_estz_core genaiexp_estz_supplemental, replace force

tempfile tf_genai
save `tf_genai', replace


********************************************************************************
* 3) Offshorability (SOC-level)
********************************************************************************

import delimited "$raw_data/horse_race/soc2018_offshore.csv", ///
    varnames(1) clear bindquote(strict) stringcols(_all)

rename soc soc_new
replace soc_new = strtrim(soc_new)
destring task_offshorability, replace force

tempfile tf_offshore
save `tf_offshore', replace


********************************************************************************
* 4) Load worker spells and attach SOC + measures
********************************************************************************

// NOTE: The raw CSV is extremely large and can take a long time to import.
// Prefer the pre-saved filtered Stata file if it exists (used elsewhere in the repo).
capture confirm file "$raw_data/Scoop_workers_positions_filtered.dta"
if _rc == 0 {
    di as text "Using $raw_data/Scoop_workers_positions_filtered.dta (faster than CSV import)."
    use "$raw_data/Scoop_workers_positions_filtered.dta", clear
}
else {
    capture confirm file "$raw_data/Scoop_workers_positions.csv"
    if _rc != 0 {
        di as error "Missing LinkedIn positions input."
        di as error "Expected either:"
        di as error "  $raw_data/Scoop_workers_positions_filtered.dta  (preferred, fast)"
        di as error "or"
        di as error "  $raw_data/Scoop_workers_positions.csv          (slow, very large)"
        exit 601
    }
    di as text "Filtered .dta not found; importing $raw_data/Scoop_workers_positions.csv (this is slow)."
    import delimited "$raw_data/Scoop_workers_positions.csv", clear bindquote(strict) ///
        stringcols(_all)
}

keep companyname role_k1000 start_date end_date
drop if companyname == "" | role_k1000 == ""

merge m:1 role_k1000 using `tf_role_soc'
drop if _merge == 2
drop _merge
drop if soc_new == ""

* GenAI merge (may be missing for some SOCs)
merge m:1 soc_new using `tf_genai'
drop if _merge == 2
drop _merge

* Offshorability merge (may be missing for some SOCs)
merge m:1 soc_new using `tf_offshore'
drop if _merge == 2
drop _merge


********************************************************************************
* 5) Restrict to the same pre-COVID job-spell window as teleworkability
********************************************************************************

gen start = date(start_date, "YMD")
gen end   = date(end_date, "YMD")
format start %td
format end   %td

drop if missing(start) | missing(end)

local end_cutoff   = date("2019-12-31", "YMD")
local start_cutoff = date("2017-12-31", "YMD")

keep if end   >= `start_cutoff'
keep if start <= `end_cutoff'


********************************************************************************
* 6) Collapse to company level (employee-weighted via spell rows)
********************************************************************************

gen byte has_genai     = !missing(genaiexp_estz_total)
gen byte has_offshore  = !missing(task_offshorability)

	collapse ///
	    (mean) genai_total        = genaiexp_estz_total ///
	           genai_core         = genaiexp_estz_core ///
	           genai_supplemental = genaiexp_estz_supplemental ///
	           offshorability     = task_offshorability ///
	           share_genai        = has_genai ///
	           share_offshorability = has_offshore ///
	    (count) n_spells = has_genai, ///
	    by(companyname)

drop if companyname == ""

label var genai_total           "Firm mean GenAI exposure (total), pre-COVID spells"
label var genai_core            "Firm mean GenAI exposure (core), pre-COVID spells"
label var genai_supplemental    "Firm mean GenAI exposure (supplemental), pre-COVID spells"
label var offshorability        "Firm mean task offshorability, pre-COVID spells"
label var share_genai           "Share of pre-COVID spells with non-missing GenAI exposure"
label var share_offshorability  "Share of pre-COVID spells with non-missing offshorability"
label var n_spells              "Number of pre-COVID worker spells used in collapse"


********************************************************************************
* 7) Save outputs
********************************************************************************

save "$processed_data/scoop_firm_horse_race.dta", replace
capture export delimited "$PROJECT_ROOT/data/samples/scoop_firm_horse_race.csv", replace

log close
