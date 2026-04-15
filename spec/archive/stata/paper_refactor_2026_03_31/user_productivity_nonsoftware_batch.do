*============================================================*
* user_productivity_nonsoftware_batch.do
* Convenience wrapper to re-run the user-productivity spec
* under four filters that document robustness outside software:
*   1) Drop NAICS 5415xx firms          (naics_software)
*   2) Drop canonical tech SOC roles    (soc_strict_new)
*   3) Drop CA/NY locations             (exclude_ca_ny)
*   4) Keep only CA/NY locations        (only_ca_ny)
*============================================================*

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

local tag_list "naics_software soc_strict_new exclude_ca_ny only_ca_ny"

foreach tag of local tag_list {
    di as txt ">>> Running user_productivity_tech_filters.do (`panel_variant', `tag')"
    do "$DIR_DO/user_productivity_tech_filters.do" "`panel_variant'" "`tag'"
}
