* Table 11: traits dual table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/11_user_productivity_traits_dual.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 11: $DIR_DO/11_user_productivity_traits_dual.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/user_productivity_traits_dual_precovid/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 11."
    exit 601
}
