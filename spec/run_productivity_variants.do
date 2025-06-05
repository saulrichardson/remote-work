* Execute productivity specifications for all user panel variants

version 18.0
set more off

do "../src/globals.do"

local variants "unbalanced balanced precovid"
local scripts "user_productivity.do user_productivity_alternative_fe.do user_productivity_initial.do"

foreach v of local variants {
    global user_panel_variant "`v'"
    di as txt "=== Variant: `v' ==="
    foreach s of local scripts {
        di as txt "Running `s' with variant `v'"
        do `"`s'"'
    }
}

exit, clear
