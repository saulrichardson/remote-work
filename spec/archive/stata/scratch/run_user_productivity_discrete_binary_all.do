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

*==========================================================================*
*  run_user_productivity_discrete_binary_all.do
*  Loop over panel variants and run the binary remote vs non-remote spec.
*==========================================================================*

args panel_variants
if "`panel_variants'" == "" local panel_variants "precovid"

local treat_list "remote nonremote"

foreach variant of local panel_variants {
    di as text "=== Running user_productivity_discrete_binary.do (`variant') ==="
    foreach treat of local treat_list {
        di as text "→ Treatment: `treat'"
        quietly do "user_productivity_discrete_binary.do" `variant' `treat'
    }
}
