*======================================================================*
* user_productivity_keep_top_metros.do
* Runs the canonical user-productivity spec while keeping only the top
* CSAs (based on the supplied mapping). Estimates the baseline spec for
* keep-top-5, keep-top-10, and keep-top-14 (all) metros.
*======================================================================*

version 17
clear all
set more off

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

di as text "Wrapper PROJECT_ROOT: $PROJECT_ROOT"

local pr_root        "$PROJECT_ROOT"
local pr_processed   "$PROCESSED_DATA"
local pr_results     "$RAW_RESULTS"
local stata_bin      "/Applications/StataNow/StataSE.app/Contents/MacOS/stata-se"

* Reassert globals for downstream scripts
global PROJECT_ROOT   "`pr_root'"
global PROCESSED_DATA "`pr_processed'"
global RAW_RESULTS    "`pr_results'"
global processed_data "`pr_processed'"
global results        "`pr_results'"

local base_panel "$processed_data/user_panel_`panel_variant'.dta"
if !fileexists("`base_panel'") {
    di as error "Panel file not found: `base_panel'"
    exit 601
}

local mapping_file "$PROJECT_ROOT/data/clean/csa_msa_top14_mapping.csv"
if !fileexists("`mapping_file'") {
    di as error "Mapping file missing: `mapping_file'. Run the Python mapper first."
    exit 601
}

tempfile csa_map
import delimited using "`mapping_file'", varnames(1) clear
tempvar max_rank
quietly summarize csa_rank
local max_rank = r(max)
save `csa_map'

local keep_targets "5 10 14"

foreach keep_count of local keep_targets {
    local effective_rank = `keep_count'
    if `effective_rank' > `max_rank' local effective_rank = `max_rank'

    use `csa_map', clear
    keep if csa_rank <= `effective_rank'
    gen byte keep_flag = 1
    keep cbsacode keep_flag
    rename cbsacode company_cbsacode
    duplicates drop
    tempfile keep_codes
    save `keep_codes'

    use "`base_panel'", clear
    capture confirm numeric variable company_cbsacode
    if _rc {
        destring company_cbsacode, replace force
        capture confirm numeric variable company_cbsacode
        if _rc {
            di as error "Variable company_cbsacode is not numeric even after destring."
            exit 459
        }
    }

    merge m:1 company_cbsacode using `keep_codes', keep(match) nogen

    qui count
    local remaining = r(N)
    di as text "→ keep_top`keep_count': remaining observations " %12.0fc `remaining'

    local variant "`panel_variant'_keeptop`keep_count'"
    save "$processed_data/user_panel_`variant'.dta", replace
    di as text "   Saved filtered panel as user_panel_`variant'.dta"

    di as text "   Running canonical spec for `variant'"
    cd "`pr_root'"
    ! "`stata_bin'" -b do spec/stata/user_productivity.do "`variant'"
}

di as result "✓ Completed keep-top CSA runs for thresholds: `keep_targets'"
