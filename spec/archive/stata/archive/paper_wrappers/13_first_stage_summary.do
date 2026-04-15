* Table 13: first-stage summary table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/user_productivity.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 13: $DIR_DO/user_productivity.do (rc=`__rc')."
    exit `__rc'
}

capture noisily do "$DIR_DO/user_productivity_alternative_fe.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 13: $DIR_DO/user_productivity_alternative_fe.do (rc=`__rc')."
    exit `__rc'
}

capture noisily do "$DIR_DO/firm_scaling.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 13: $DIR_DO/firm_scaling.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/user_productivity_precovid/first_stage.csv" ///
    "$results/user_productivity_alternative_fe_precovid/first_stage_fstats.csv" ///
    "$results/firm_scaling/first_stage.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected first-stage input for table 13: `f'"
        exit 601
    }
}
