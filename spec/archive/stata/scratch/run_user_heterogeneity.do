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

* Run both user productivity heterogeneity scripts (IV + OLS after recent changes)
clear all
set more off

display as text "[run_user_heterogeneity] starting in: `c(pwd)'"

* Ensure project-relative globals are set
* Load project globals (paths) – resolve relative to project root
do "src/globals.do"
display as text "[run_user_heterogeneity] processed_data: $processed_data"
display as text "[run_user_heterogeneity] results:        $results"

* Sanity: confirm processed panel is available
cap confirm file "$processed_data/user_panel_precovid.dta"
if _rc {
    di as error "[run_user_heterogeneity] Missing panel: $processed_data/user_panel_precovid.dta"
}

* Move to the spec directory so relative paths in scripts match
cd "`c(pwd)'/spec" // ensure we are in spec when calling the scripts
display as text "[run_user_heterogeneity] cd -> `c(pwd)'"

* Modal vs. Non-Modal MSA (precovid panel)
do "user_productivity_modal_msa.do" precovid
cap confirm file "../results/raw/het_modal_base_precovid_3/var5_modal_base_ols.csv"
if _rc di as error "[run_user_heterogeneity] Warning: OLS modal CSV not found yet"

* Distance buckets (precovid panel) – run 3 bins and 2 bins
do "user_productivity_distance_split.do" precovid 3
cap confirm file "../results/raw/het_dist_base_precovid_3/var5_distance_base_ols.csv"
if _rc di as error "[run_user_heterogeneity] Warning: OLS distance CSV (3 bins) not found"

do "user_productivity_distance_split.do" precovid 2
cap confirm file "../results/raw/het_dist_base_precovid_2/var5_distance_base_ols.csv"
if _rc di as error "[run_user_heterogeneity] Warning: OLS distance CSV (2 bins) not found"

exit
