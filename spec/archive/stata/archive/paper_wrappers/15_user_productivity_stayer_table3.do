* Table 15: stayer table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/user_productivity_initial_stayer.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 15: $DIR_DO/user_productivity_initial_stayer.do (rc=`__rc')."
    exit `__rc'
}

capture noisily do "$DIR_DO/user_productivity_alternative_fe_stayer.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 15: $DIR_DO/user_productivity_alternative_fe_stayer.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/user_productivity_initial_precovid_stayer/consolidated_results.csv" ///
    "$results/user_productivity_alternative_fe_precovid_stayer/consolidated_results.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 15: `f'"
        exit 601
    }
}
