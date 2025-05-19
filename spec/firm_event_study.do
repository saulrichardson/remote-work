do "../src/globals.do"
local specname  "firm_event_study"
local result_path "$clean_results"
// capture mkdir "`result_path'"

use "$processed_data/firm_panel.dta", clear

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

restore

*-----------------------------------------------------------
* Prove that index is correct
*-----------------------------------------------------------
gen dummy_2019h2 = time`idx19h2'
label var dummy_2019h2 "Indicator for 2019H2"
tab yh dummy_2019h2

*---------------------------------------------------------
* Generate time interaction variables for all periods
*---------------------------------------------------------

preserve
contract yh, freq(count_yh)
local total_periods = _N
restore
	
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
	local endog_vars  `endog_vars'  rem_`t' rem_start_`t'
	local instr_vars  `instr_vars'  tel_`t' tel_start_`t'
	local startup_vars `startup_vars' startup_`t'
}


local outcome_vars "growth_rate_we leave_rate_we join_rate_we"

foreach outcome of local outcome_vars {

	eststo clear
	
	reghdfe `outcome' `endog_vars' `startup_vars', ///
		absorb(firm_id yh) cluster(firm_id)
		

	matrix define escoef1 = J(`total_periods',3,0)
	
	local before_idx = (`idx19h2'-1)
	local after_idx = (`idx19h2'+1)
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

	local ylab: variable label `outcome'
	
	coefplot (matrix(escoef1[,1]), ci((escoef1[,2] escoef1[,3])) ciopts(lc(navy*.5))) , ///
		drop(*.year* _cons) vertical yline(0, lc(gs13) lw(thin)) ///
		xline(8.0, lp("-.") lc(black)) ///
		coeflabels(r1 = " " r2 = "2017" r3 = " " r4 = "2018" r5 = " " r6 = "2019" r7 = " " r8 = "2020" r9 = " " r10 = "2021" r11 = " " r12 = "2022") ///
		graphregion(color(white)) xtitle("Year") yline(0, lc(black)) ///
		bgcolor(white) graphregion(color(white)) label ytitle("`ylab'")
	
	graph export "`result_path'/ols_`outcome'.png", replace
	
	
	eststo clear
	ivreghdfe `outcome' (`endog_vars' = `instr_vars') `startup_vars', ///
		absorb(firm_id yh) cluster(firm_id)	

	matrix define escoef1 = J(`total_periods',3,0)
	
	local before_idx = (`idx19h2'-1)
	local after_idx = (`idx19h2'+1)
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

	local ylab: variable label `outcome'
	
	coefplot (matrix(escoef1[,1]), ci((escoef1[,2] escoef1[,3])) ciopts(lc(navy*.5))) , ///
		drop(*.year* _cons) vertical yline(0, lc(gs13) lw(thin)) ///
		xline(8.0, lp("-.") lc(black)) ///
		coeflabels(r1 = " " r2 = "2017" r3 = " " r4 = "2018" r5 = " " r6 = "2019" r7 = " " r8 = "2020" r9 = " " r10 = "2021" r11 = " " r12 = "2022") ///
		graphregion(color(white)) xtitle("Year") yline(0, lc(black)) ///
		bgcolor(white) graphregion(color(white)) label ytitle("`ylab'")
	

	graph export "`result_path'/iv_`outcome'.png", replace
	
}

