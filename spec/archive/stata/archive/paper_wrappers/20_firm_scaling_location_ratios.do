* Table 20: firm location ratios

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/20_firm_scaling_location_ratios.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 20: $DIR_DO/20_firm_scaling_location_ratios.do (rc=`__rc')."
    exit `__rc'
}

capture confirm file "$results/firm_scaling_locations_per_employee/consolidated_results.csv"
if _rc {
    di as error "Missing expected raw output for table 20."
    exit 601
}
