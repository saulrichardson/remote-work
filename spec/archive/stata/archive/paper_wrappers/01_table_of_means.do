* Table 1: descriptive table of means

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

foreach f in "$processed_data/firm_panel.dta" "$processed_data/user_panel_precovid.dta" {
    capture confirm file "`f'"
    if _rc {
        di as error "Missing required input for table_of_means: `f'"
        exit 601
    }
}

di as result "Table 1 uses cleaned panels directly; no Stata regression step is required."
