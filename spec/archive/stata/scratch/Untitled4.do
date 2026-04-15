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



*============================================================*
* user_productivity.do
* Generates the baseline user-level regressions that quantify how firms'
* remote-work adoption affects individual GitHub contribution ranks.
* The script can be run on alternative user-panel variants (default: precovid),
* estimates both OLS and 2SLS specifications with firm, user, and time fixed
* effects, and records the associated first-stage diagnostics based on the
* teleworkability instrument from Dingel & Neiman.
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional variant argument *before* sourcing globals --------------
* --------------------------------------------------------------------------

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_`panel_variant'
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


// 0) Setup environment
do "../globals.do"

// 1) Load worker‐level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear

