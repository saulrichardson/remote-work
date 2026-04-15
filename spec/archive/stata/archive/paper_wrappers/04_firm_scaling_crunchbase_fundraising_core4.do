* Table 4: Crunchbase fundraising core outcomes

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/04_firm_scaling_crunchbase_fundraising_core4.do"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 4: $DIR_DO/04_firm_scaling_crunchbase_fundraising_core4.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/firm_scaling_crunchbase_fundraising_core4/consolidated_results.csv" ///
    "$results/firm_scaling_crunchbase_fundraising_core4/outcome_diagnostics.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 4: `f'"
        exit 601
    }
}
