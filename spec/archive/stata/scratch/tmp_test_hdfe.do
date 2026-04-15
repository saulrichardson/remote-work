// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

clear all
set more off

use "data/processed/user_panel_precovid.dta", clear

keep if inrange(year(dofh(yh)), 2018, 2019)

capture confirm numeric variable salary
if _rc {
    destring salary, replace
}

gen double lwage = ln(salary)

capture confirm numeric variable msa_id
if _rc {
    encode msa, gen(msa_id)
}

capture confirm numeric variable firm_id
if _rc {
    encode companyname, gen(firm_id)
}

capture confirm numeric variable title_id
if _rc {
    encode title, gen(title_id)
}

hdfe lwage i.msa_id, absorb(firm_id title_id yh) generate(res_)

describe res_*
