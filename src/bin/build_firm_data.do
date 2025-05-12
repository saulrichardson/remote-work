*------------------------------------------------------------*
* src/build_firm_data.do
* Build and clean firm-level data into master_firm.dta.
*------------------------------------------------------------*

* 0) load globals
do "src/globals2.do"

* 1) Generate modal MSA per firm
do "../do/firm_msa.do"

* 2) Generate modal role per firm
do "../do/firm_roles.do"

* 3) [Optional] Additional firm-level merges or calculations here
*    e.g., merge with flexibility scores, founding dates

* 4) Save firm-level master panel
capture mkdir "$data"
save "$data/master_firm.dta", replace

di as result "✅ Firm-level data build complete: $data/master_firm.dta"