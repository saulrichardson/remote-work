* Table 7: mechanisms on the keep-remote margin

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/07_user_mechanisms_keep_remote.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 7: $DIR_DO/07_user_mechanisms_keep_remote.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/user_mechanisms_keep_remote_precovid/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 7."
    exit 601
}
