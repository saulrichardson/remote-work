* Table 18: Crunchbase FE robustness table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/18_firm_scaling_crunchbase_fundraising_core4_fe_robustness.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 18: $DIR_DO/18_firm_scaling_crunchbase_fundraising_core4_fe_robustness.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/firm_scaling_crunchbase_fundraising_core4_fe_robustness/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 18."
    exit 601
}
