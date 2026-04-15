* Table 16: industry and HQ-state shocks

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/16_user_productivity_industry_hqstate_shocks.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 16: $DIR_DO/16_user_productivity_industry_hqstate_shocks.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/user_productivity_industry_hqstate_shocks_precovid/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 16."
    exit 601
}
