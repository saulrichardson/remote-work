*======================================================================*
* user_productivity_drop_top_metros.do
* Re-runs the canonical user-productivity spec after excluding the
* top CSAs (by the provided screenshot list) based on firm MSAs.
* The script now drops two sets of CSAs (capped at the 14 enumerated
* metros), saves filtered panels, and calls the baseline spec for each:
*  - Drop Top 5
*  - Drop Top 14 (drops all mapped CSAs)
*======================================================================*

version 17
clear all
set more off

*---- Arguments -------------------------------------------------------*
args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

*---- Bootstrap paths -------------------------------------------------*
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"
di as text "Wrapper PROJECT_ROOT: $PROJECT_ROOT"

* Cache path globals so we can reapply them before recursive runs
local pr_root        "$PROJECT_ROOT"
local pr_processed   "$PROCESSED_DATA"
local pr_results     "$RAW_RESULTS"
local stata_bin      "/Applications/Stata/StataSE.app/Contents/MacOS/stata-se"
if !fileexists("`stata_bin'") local stata_bin "/Applications/StataNow/StataSE.app/Contents/MacOS/stata-se"

* Ensure downstream specs see the same globals (in case they were cleared)
global PROJECT_ROOT   "`pr_root'"
global PROCESSED_DATA "`pr_processed'"
global RAW_RESULTS    "`pr_results'"
global processed_data "`pr_processed'"
global results        "`pr_results'"

*---- Files -----------------------------------------------------------*
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

*---- Drop thresholds -------------------------------------------------*
* Include the intermediate cut (top 10) so we can form four scenarios:
* drop5, drop10, keep5, keep10
local drop_targets "5 10 14"

foreach drop_count of local drop_targets {
    local effective_rank = `drop_count'
    if `effective_rank' > `max_rank' local effective_rank = `max_rank'

    use `csa_map', clear
    keep if csa_rank <= `effective_rank'
    gen byte drop_flag = 1
    keep cbsacode drop_flag
    rename cbsacode company_cbsacode
    duplicates drop
    tempfile drop_codes
    save `drop_codes'

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

    merge m:1 company_cbsacode using `drop_codes', keep(master match) nogen
    drop if drop_flag == 1
    drop drop_flag

    qui count
    local remaining = r(N)
    di as text "→ drop_top`drop_count': remaining observations " %12.0fc `remaining'

    local variant "`panel_variant'_droptop`drop_count'"
    save "$processed_data/user_panel_`variant'.dta", replace
    di as text "   Saved filtered panel as user_panel_`variant'.dta"

    di as text "   Running canonical spec for `variant' via external Stata call"
    cd "`pr_root'"
    ! "`stata_bin'" -b do spec/stata/user_productivity.do "`variant'"

    di as text "   Running firm×user FE spec for `variant'"
    ! "`stata_bin'" -b do spec/stata/scratch/user_productivity_firmbyuser.do "`variant'"
}

di as result "✓ Completed drop-top CSA runs for thresholds: `drop_targets'"
