* Table 17: firm scaling with industry and HQ-state shocks

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/17_firm_scaling_industry_hqstate_shocks.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 17: $DIR_DO/17_firm_scaling_industry_hqstate_shocks.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/firm_scaling_industry_hqstate_shocks/consolidated_results.csv"
if _rc {
    di as error "Missing expected main raw output for table 17."
    exit 601
}

capture confirm file "$results/firm_scaling_industry_hqstate_shocks/first_stage_fstats.csv"
if _rc {
    di as error "Missing expected first-stage raw output for table 17."
    exit 601
}
