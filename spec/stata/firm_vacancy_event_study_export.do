local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"



local specname  "firm_vacancy_event_study"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_path "$results/`specname'"
cap mkdir "`result_path'"

use "$processed_data/firm_panel.dta", clear

*-----------------------------------------------------------
* Merge vacancy panel metrics needed for event study
*-----------------------------------------------------------
preserve
    import delimited using "$processed_data/vacancy/firm_halfyear_panel_MERGED_POST.csv", ///
        clear varnames(1)

    local required_csv_vars companyname yh vacancies hires_to_vacancies_winsor
    foreach v of local required_csv_vars {
        capture confirm variable `v'
        if _rc {
            di as error "Missing required vacancy variable: `v'"
            exit 198
        }
    }

    tempvar y_tmp h_tmp yh_num
    gen double `y_tmp' = real(substr(yh, 1, 4))
    gen double `h_tmp' = real(substr(yh, 6, 1))
    gen double `yh_num' = (`y_tmp' - 1960)*2 + (`h_tmp' - 1)
    format `yh_num' %th
    rename yh yh_str
    rename `yh_num' yh

    capture confirm variable companyname_c
    if (_rc) {
        gen companyname_c = lower(companyname)
    }
    else {
        replace companyname_c = lower(companyname)
    }
    keep companyname companyname_c yh vacancies hires_to_vacancies_winsor
    tempfile vac
    save `vac'
restore

gen companyname_c = lower(companyname)
merge 1:1 companyname_c yh using `vac'

count if _merge == 2
local using_only = r(N)
count if _merge == 1
local master_only = r(N)
local matched = _N - `using_only' - `master_only'
di as text "Merge summary (vacancy): matched=`matched' using-only=`using_only' master-only=`master_only'"

keep if _merge == 3
drop _merge

capture drop vacancies_thousands
gen double vacancies_thousands = vacancies/1000
label var vacancies_thousands "Vacancies (Thousands)"

capture confirm variable hires_to_vacancies_winsor
if _rc == 0 label var hires_to_vacancies_winsor "Hires per vacancy (winsor 1/99, ≥5 vacancies)"

*-----------------------------------------------------------
* Create half-year dummies: time1 ... timeN
*-----------------------------------------------------------
tab yh, gen(time)

*-----------------------------------------------------------
* Identify which index corresponds to 2019H2
*    (Preserve-restore trick to find the distinct yh values
*    and their ascending order index)
*-----------------------------------------------------------
tempvar tmpindex
tempvar foundindex

preserve

contract yh          // one row per distinct yh
sort yh              // must be sorted in ascending order
gen `tmpindex' = _n  // row index from 1 to # of distinct yh

// Compute numeric value for 2019H2
local target19h2 = yh(2019, 2)

quietly summarize `tmpindex' if yh == `target19h2'
local idx19h2 = r(mean)
display "Index for 2019H2 is `idx19h2'"

* Build half-year label lookup for CSV export
* Use %th format (e.g., "2019h2") and capitalize the "h" -> "H"
gen str7 period_label = subinstr(string(yh, "%th"), "h", "H", .)
keep yh `tmpindex' period_label
rename `tmpindex' period
tempfile yhmap
save `yhmap'

restore

*-----------------------------------------------------------
* Prove that index is correct
*-----------------------------------------------------------
gen dummy_2019h2 = time`idx19h2'
label var dummy_2019h2 "Indicator for 2019H2"
tab yh dummy_2019h2

*---------------------------------------------------------
* Count total periods
*---------------------------------------------------------
preserve
contract yh, freq(count_yh)
local total_periods = _N
restore
	
*---------------------------------------------------------
* Generate time interaction variables for all periods
*---------------------------------------------------------
forval t = 1/`total_periods' {
	gen rem_`t'       = remote * time`t'
	gen startup_`t'   = startup * time`t'
	gen rem_start_`t' = remote * time`t' * startup
	gen tel_`t'       = teleworkable * time`t'
	gen tel_start_`t' = teleworkable * time`t' * startup
}

*---------------------------------------
* Build macros for IV
*---------------------------------------
local endog_vars  ""
local instr_vars  ""
local startup_vars ""

forval t = 1/`total_periods'{
	if `t' == `idx19h2' {
		continue // skip over 2019H2
	}
	local endog_vars   `endog_vars'  rem_`t' rem_start_`t'
	local instr_vars   `instr_vars'  tel_`t' tel_start_`t'
	local startup_vars `startup_vars' startup_`t'
}

local outcome_vars "vacancies_thousands hires_to_vacancies_winsor"

foreach outcome of local outcome_vars {

	* ================= OLS =================
	eststo clear
	reghdfe `outcome' `endog_vars' `startup_vars', ///
		absorb(firm_id yh) cluster(firm_id)

	matrix define escoef1 = J(`total_periods',3,0)
	
	local before_idx = (`idx19h2' - 1)
	local after_idx  = (`idx19h2' + 1)
	forval i=1/`before_idx' {
		matrix escoef1[`i',1] = _b[rem_start_`i']
		matrix escoef1[`i',2] = _b[rem_start_`i'] - _se[rem_start_`i']*1.96
		matrix escoef1[`i',3] = _b[rem_start_`i'] + _se[rem_start_`i']*1.96
	}
	forval i=`after_idx'/`total_periods' {
		matrix escoef1[`i',1] = _b[rem_start_`i']
		matrix escoef1[`i',2] = _b[rem_start_`i'] - _se[rem_start_`i']*1.96
		matrix escoef1[`i',3] = _b[rem_start_`i'] + _se[rem_start_`i']*1.96
	}

	* Keep ylab retrieval for minimal change (not used below)
	local ylab: variable label `outcome'
	
	* Save coefficients to CSV (OLS)
	matrix colnames escoef1 = b lb ub
	preserve
		clear
		svmat double escoef1, names(col)
		gen period     = _n
		gen event_time = period - `idx19h2'
		gen omitted    = period == `idx19h2'
		replace b  = . if omitted
		replace lb = . if omitted
		replace ub = . if omitted
		merge 1:1 period using `yhmap', nogen
		gen str8  estimator = "OLS"
		gen str80 outcome   = "`outcome'"
		order outcome estimator period period_label event_time omitted b lb ub yh
		export delimited using "`result_path'/ols_`outcome'.csv", replace
	restore
	
	
	* ================= IV =================
	eststo clear
	ivreghdfe `outcome' (`endog_vars' = `instr_vars') `startup_vars', ///
		absorb(firm_id yh) cluster(firm_id)

	matrix define escoef1 = J(`total_periods',3,0)
	
	local before_idx = (`idx19h2' - 1)
	local after_idx  = (`idx19h2' + 1)
	forval i=1/`before_idx' {
		matrix escoef1[`i',1] = _b[rem_start_`i']
		matrix escoef1[`i',2] = _b[rem_start_`i'] - _se[rem_start_`i']*1.96
		matrix escoef1[`i',3] = _b[rem_start_`i'] + _se[rem_start_`i']*1.96
	}
	forval i=`after_idx'/`total_periods' {
		matrix escoef1[`i',1] = _b[rem_start_`i']
		matrix escoef1[`i',2] = _b[rem_start_`i'] - _se[rem_start_`i']*1.96
		matrix escoef1[`i',3] = _b[rem_start_`i'] + _se[rem_start_`i']*1.96
	}

	* Keep ylab retrieval for minimal change (not used below)
	local ylab: variable label `outcome'
	
	* Save coefficients to CSV (IV)
	matrix colnames escoef1 = b lb ub
	preserve
		clear
		svmat double escoef1, names(col)
		gen period     = _n
		gen event_time = period - `idx19h2'
		gen omitted    = period == `idx19h2'
		replace b  = . if omitted
		replace lb = . if omitted
		replace ub = . if omitted
		merge 1:1 period using `yhmap', nogen
		gen str8  estimator = "IV"
		gen str80 outcome   = "`outcome'"
		order outcome estimator period period_label event_time omitted b lb ub yh
		export delimited using "`result_path'/iv_`outcome'.csv", replace
	restore
	
}
