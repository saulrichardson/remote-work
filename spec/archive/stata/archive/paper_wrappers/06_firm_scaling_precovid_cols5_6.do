* Table 6: firm scaling vacancy columns

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/06_firm_scaling_precovid_cols5_6.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 6: $DIR_DO/06_firm_scaling_precovid_cols5_6.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/firm_scaling_vacancy_outcomes_htv2_95/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 6."
    exit 601
}
