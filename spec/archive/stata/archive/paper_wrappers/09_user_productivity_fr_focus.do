* Table 9: fully-remote focus comparisons

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/09_user_productivity_fr_focus.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 9: $DIR_DO/09_user_productivity_fr_focus.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/user_productivity_fr_focus_precovid_fr_vs_all/consolidated_results.csv" ///
    "$results/user_productivity_fr_focus_precovid_fr_vs_hyb/consolidated_results.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 9: `f'"
        exit 601
    }
}
