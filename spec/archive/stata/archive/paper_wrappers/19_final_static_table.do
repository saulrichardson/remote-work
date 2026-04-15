* Table 19: repo-local static summary table

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do."
    exit 601
}
do "`__bootstrap'"

capture confirm file "$DIR_ROOT/writeup/static_tables/Final.tex"
if _rc {
    di as error "Missing repo-local static source for table 19 (writeup/static_tables/Final.tex)."
    exit 601
}

di as result "Table 19 is currently a repo-local static table; no Stata regression step is required."
