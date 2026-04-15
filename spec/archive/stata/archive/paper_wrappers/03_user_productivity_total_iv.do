* Table 3: user productivity baseline IV single table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/user_productivity_initial.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 3: $DIR_DO/user_productivity_initial.do (rc=`__rc')."
    exit `__rc'
}

capture noisily do "$DIR_DO/user_productivity_alternative_fe.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 3: $DIR_DO/user_productivity_alternative_fe.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/user_productivity_initial_precovid/consolidated_results.csv" ///
    "$results/user_productivity_alternative_fe_precovid/consolidated_results.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 3: `f'"
        exit 601
    }
}
