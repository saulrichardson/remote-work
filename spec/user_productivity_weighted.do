

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"
local specname user_productivity_`panel_variant'_weighted
capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

// 0) Setup environment
do "../src/globals.do"



import delimited "$raw_data/Scoop_alt.csv", clear

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th

collapse (last) date (sum) join leave, by(companyname yh)

tempfile join_leave
keep companyname yh join leave
save `join_leave'


import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th

// Drop one-off observations in June 2022
drop if date == 22797


// Collapse to have one observation per firm-half-year, and calculate growth & rates:
collapse (last) total_employees date (sum) join leave, by(companyname yh)

drop join leave
merge 1:1 companyname yh using `join_leave'
drop _merge

encode companyname, gen(company_numeric)
xtset company_numeric yh
sort company_numeric yh

gen growth_rate = (total_employees / L.total_employees) - 1 if _n > 1
gen join_rate = join / L.total_employees if _n > 1
gen leave_rate = leave / L.total_employees if _n > 1

xtset, clear

winsor2 growth_rate join_rate leave_rate, cuts(1 99) suffix(_we)
label variable growth_rate_we "Winsorized growth rate [1,99]"
label variable join_rate_we "Winsorized join rate [1,99]"
label variable leave_rate_we "Winsorized leave rate [1,99]"

drop growth_rate join_rate leave_rate company_numeric

keep companyname yh	total_employees

tempfile employee_counts
save `employee_counts'


// 1) Load worker‐level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge

merge m:1 companyname yh using `employee_counts'


// 2) Prepare output dir & reset any old postfile
*--------------------------------------------------------------------------*
* Results are now *always* written to <specname> _<panel‐variant> (e.g.,
*   "user_productivity_unbalanced") so the output folder unambiguously states
* which user‐panel sample was used.  No silent fallback for the default
* sample.
*--------------------------------------------------------------------------*

local result_dir  "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
*--- postfile header (main results) -------------------------------------------
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace


*------------------------------------------------------------------
*  First-stage results → first_stage_fstats.csv
*------------------------------------------------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace
	

local outcomes total_contributions_q100 
local fs_done 0

gen weight = 1/total_employees
foreach y of local outcomes {
    di as text "→ Processing outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----- OLS -----
    reghdfe `y' var3 var5 var4 [pweight = weight], absorb(user_id#firm_id yh) ///
        vce(cluster user_id)
		
	local N = e(N) 
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
		*--- inside the OLS loop ------------------------------------------------------
        post handle ("OLS") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')                 // dot for rkf, then nobs
    }

    // ----- IV (2nd‐stage) -----
    ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4 [pweight = weight], ///
        absorb(user_id#firm_id yh) vce(cluster user_id) savefirst
		
    local rkf = e(rkf)
	local N = e(N) 
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
		*--- inside the IV loop -------------------------------------------------------
        post handle ("IV") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')            // rkf, then nobs
    }

	if !`fs_done' {
		
		matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

		/* -------- var3 first stage -------------------------------- */
		estimates restore _ivreg2_var3
		local N_fs = e(N)
		foreach p in var6 var7 var4 {
			local b    = _b[`p']
			local se   = _se[`p']
			local t    = `b'/`se'
			local pval = 2*ttail(e(df_r), abs(`t'))

			post handle_fs ("var3") ("`p'") ///
							(`b') (`se') (`pval') ///
							(`F3') (`rkf') (`N_fs')
		}

		/* -------- var5 first stage -------------------------------- */
		estimates restore _ivreg2_var5
		local N_fs = e(N)
		foreach p in var6 var7 var4 {
			local b    = _b[`p']
			local se   = _se[`p']
			local t    = `b'/`se'
			local pval = 2*ttail(e(df_r), abs(`t'))

			post handle_fs ("var5") ("`p'") ///
							(`b') (`se') (`pval') ///
							(`F5') (`rkf') (`N_fs')
		}

		local fs_done 1
	}
}


// 4) Close & export to CSV
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

* --- write first-stage CSV -----------------------------------------
postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
        replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
capture log close
