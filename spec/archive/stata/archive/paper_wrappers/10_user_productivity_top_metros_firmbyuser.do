* Table 10: top-metro firm-by-user FE table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/user_productivity_keep_top_metros.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 10: $DIR_DO/user_productivity_keep_top_metros.do (rc=`__rc')."
    exit `__rc'
}

capture noisily do "$DIR_DO/user_productivity_drop_top_metros.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 10: $DIR_DO/user_productivity_drop_top_metros.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/user_productivity_precovid_keeptop5/consolidated_results.csv" ///
    "$results/user_productivity_precovid_keeptop10/consolidated_results.csv" ///
    "$results/user_productivity_precovid_droptop5/consolidated_results.csv" ///
    "$results/user_productivity_precovid_droptop10/consolidated_results.csv" ///
    "$results/user_productivity_firmbyuser_precovid_keeptop5/consolidated_results.csv" ///
    "$results/user_productivity_firmbyuser_precovid_keeptop10/consolidated_results.csv" ///
    "$results/user_productivity_firmbyuser_precovid_droptop5/consolidated_results.csv" ///
    "$results/user_productivity_firmbyuser_precovid_droptop10/consolidated_results.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 10: `f'"
        exit 601
    }
}
