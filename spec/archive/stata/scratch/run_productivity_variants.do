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
log using "$LOG_DIR/run_productivity_variants.log", replace text




* Execute productivity specifications for all user panel variants

// -------------------------------------------------------------------------
//  Master driver – run all productivity & mechanisms specs for every panel
//  variant.  A single *driver log* is written in addition to the per-script
//  logs created by each individual do-file.
// -------------------------------------------------------------------------

// Root-level globals & paths ------------------------------------------------
do "../globals.do"

// Create log directory if missing -----------------------------------------

local variants "unbalanced balanced precovid"
local scripts  "user_productivity.do user_productivity_alternative_fe.do user_productivity_initial.do user_mechanisms.do user_mechanisms_lean.do"

foreach v of local variants {
    di as txt "=== Variant: `v' ==="
    foreach s of local scripts {
        di as txt "Running `s' with variant `v'"
        quietly do `"`s'"' "`v'"
    }
}

log close

exit, clear
