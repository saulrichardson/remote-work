* Table 12: non-software robustness table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture noisily do "$DIR_DO/user_productivity_nonsoftware_batch.do" "precovid"
local __rc = _rc
if `__rc' {
    di as error "Underlying spec failed for table 12: $DIR_DO/user_productivity_nonsoftware_batch.do (rc=`__rc')."
    exit `__rc'
}

foreach f in ///
    "$results/user_productivity_techfilter_precovid_naics_software/consolidated_results.csv" ///
    "$results/user_productivity_techfilter_precovid_soc_strict_new/consolidated_results.csv" ///
    "$results/user_productivity_precovid_exclude_ca_ny/consolidated_results.csv" ///
{
    capture confirm file "`f'"
    if _rc {
        di as error "Missing expected raw output for table 12: `f'"
        exit 601
    }
}
