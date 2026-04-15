* Table 5: firm scaling growth, join, and leave columns

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/firm_scaling_initial.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 5: $DIR_DO/firm_scaling_initial.do (rc=`__rc')."
    exit `__rc'
}

capture noisily do "$DIR_DO/firm_scaling.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 5: $DIR_DO/firm_scaling.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/firm_scaling_initial/consolidated_results.csv" ///
    "$results/firm_scaling/consolidated_results.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 5: `f'"
        exit 601
    }
}
