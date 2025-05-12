

/*************************************************************************
 * 0) Define paths and specification
 *************************************************************************/
do "../globals2.do"

// Local specification name
local specname "company_scaling_tables_adj"

// Create a global output path combining the two
local output_path "$results/`specname'"

// Ensure the output folders exist:
capture mkdir "`output_path'"
capture mkdir "`output_path'/OLS"
capture mkdir "`output_path'/IV"

/*------------------------------------------------------------------------------
   1A. Positions Data
------------------------------------------------------------------------------*/

import delimited "/Users/saul/Dropbox/Remote Work Startups/New/Data/Scoop_alt.csv", clear

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


import delimited "$scoop/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

// Converting date to Stata format and creating half-year indicators:
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

winsor2 growth_rate join_rate leave_rate, cuts(1 99) suffix(_we)
label variable growth_rate_we "Winsorized growth rate [1,99]"
label variable join_rate_we "Winsorized join rate [1,99]"
label variable leave_rate_we "Winsorized leave rate [1,99]"

drop growth_rate join_rate leave_rate company_numeric


/*************************************************************************
 * 4) Merge firm-level characteristics into worker-level data
 *************************************************************************/

// Merge teleworkable data:
merge m:1 companyname using "$scoop/scoop_firm_tele_2.dta"
drop if _merge == 2
drop _merge

// Merge with flexibility measures (e.g., remote/flexibility scores):
merge m:1 companyname using "$scoop/Scoop_clean_public.dta"
drop if _merge == 2
drop _merge

// Merge with founding year data:
merge m:1 companyname using "$scoop/Scoop_founding.dta"
drop if _merge == 2
drop _merge

// Compute firm age and encode IDs:
gen age = 2020 - founded
label var age "Firm age as of 2020"
encode companyname, gen(firm_id)

// Define startup indicator (age ≤ 10) and COVID period indicator (yh ≥ 120)
gen startup = (age <= 10)
gen covid = yh >= 120

// Rename remote variable:
rename flexibility_score2 remote

drop if missing(remote, covid, startup, teleworkable)

// Generate key interactions:
gen var3 = remote * covid
gen var4 = covid * startup
gen var5 = remote * covid * startup
gen var6 = covid * teleworkable
gen var7 = startup * covid * teleworkable

// Save the clean snapshot:
tempfile snapshot_clean
save `snapshot_clean', replace


/*************************************************************************
 * Revised Regression Code:
 *    - Use only the "min" panel
 *    - Report only pre-COVID means and RFK F stat in main IV output
 *    - Save the first stages (partial F-statistics for var3 and var5)
 *************************************************************************/

// Reload the snapshot and lock in the "min" panel:
use `snapshot_clean', clear
di as text ">>> ENFORCING MIN PANEL"

// Determine the global minimum half-year (yh):
summarize yh
local global_min = r(min)

// For each firm, compute the minimum half-year:
bys firm_id: egen min_time = min(yh)

// (Optional) Get total half-year periods in the sample:
preserve
    contract yh, freq(count_yh)
    local total_periods = _N
restore

// Keep only firms with the global minimum time:
keep if min_time == `global_min'
drop min_time

// Lock in file names (panel_suffix is "min"):
local panel_suffix "min"
local ols_file  "`output_path'/OLS/scaling_ols_`panel_suffix'.tex"
local iv_file   "`output_path'/IV/scaling_iv_`panel_suffix'.tex"
local var3_file "`output_path'/IV/scaling_iv_fs_var3_`panel_suffix'.tex"
local var5_file "`output_path'/IV/scaling_iv_fs_var5_`panel_suffix'.tex"

// Define outcome variables (all three outcomes):
local outcome_vars growth_rate_we join_rate_we leave_rate_we

// Initialize counters for file writing:
local first_ols  = 1
local first_iv   = 1
local first_iv_fs3 = 1
local first_iv_fs5 = 1

// Loop over each outcome variable:
foreach outcome of local outcome_vars {
    
    di as text "Processing outcome: `outcome'"
    
    //----- OLS Regression -----
    reghdfe `outcome' var3 var5 var4, absorb(firm_id yh) cluster(firm_id)
    
    // Compute pre-COVID mean (using only observations where covid == 0)
    quietly summarize `outcome' if e(sample) & covid == 0
    local precovid_mean = r(mean)
    
    // Write OLS results (replace on first iteration, then append)
    if `first_ols' == 1 {
        outreg2 using "`ols_file'", tex(frag) replace ///
            addstat("Pre-COVID Y-Mean", `precovid_mean')
        local first_ols = 0
    }
    else {
        outreg2 using "`ols_file'", tex(frag) append ///
            addstat("Pre-COVID Y-Mean", `precovid_mean')
    }
    
    
    //----- IV Regression -----
    ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) cluster(firm_id) savefirst
    
    // Compute pre-COVID mean for IV sample:
    quietly summarize `outcome' if e(sample) & covid == 0
    local precovid_mean = r(mean)
    
    // Write IV results, reporting only the RFK F statistic along with the pre-COVID mean:
    if `first_iv' == 1 {
        outreg2 using "`iv_file'", tex(frag) replace ///
            addstat("Pre-COVID Y-Mean", `precovid_mean', ///
                    "K-P rk Wald F", e(rkf))
        local first_iv = 0
    }
    else {
        outreg2 using "`iv_file'", tex(frag) append ///
            addstat("Pre-COVID Y-Mean", `precovid_mean', ///
                    "K-P rk Wald F", e(rkf))
    }
    
    //----- Save First Stage Outputs -----
    // Extract the first stage information
    matrix FS = e(first)
    local partialF_3 = FS[4,1]  // row 4, col 1 gives partial F for var3
    local partialF_5 = FS[4,2]  // row 4, col 2 gives partial F for var5
    
    // Restore the saved first stage for var3 and output:
    estimates restore _ivreg2_var3
    if `first_iv_fs3' == 1 {
        outreg2 using "`var3_file'", tex(frag) replace ///
            addstat("Partial F(var3)", `partialF_3')
        local first_iv_fs3 = 0
    }
    else {
        outreg2 using "`var3_file'", tex(frag) replace ///
            addstat("Partial F(var3)", `partialF_3')
    }
    
    // Restore the saved first stage for var5 and output:
    estimates restore _ivreg2_var5
    if `first_iv_fs5' == 1 {
        outreg2 using "`var5_file'", tex(frag) replace ///
            addstat("Partial F(var5)", `partialF_5')
        local first_iv_fs5 = 0
    }
    else {
        outreg2 using "`var5_file'", tex(frag) replace ///
            addstat("Partial F(var5)", `partialF_5')
    }
}

display as text ">>> All loops completed successfully!"
