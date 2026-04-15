* Table 8: wage FE variants (log salary)

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/08_user_wage_fe_variants_log_salary.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 8: $DIR_DO/08_user_wage_fe_variants_log_salary.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/user_wage_fe_variants_precovid/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 8."
    exit 601
}
