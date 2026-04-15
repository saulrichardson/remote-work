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

*============================================================*
* user_productivity_remote_eng_split.do
* ------------------------------------------------------------
* 2×2 productivity comparison:
*   Remote × Post effect by pre-COVID engineer share terciles
*   (top tercile = "HighEng"). Outcome: total contributions.
*   Spec mirrors main productivity regressions (firm+user
*   fixed effects within firm, half-year FE; clustered by user).
*   Reports OLS and IV coefficients for:
*       - Remote × Post × HighEng
*       - Remote × Post × LowEng
*       - Difference (High - Low)
*   IV instruments interact WFH exposure with High/LowEng.
*============================================================*

clear all
set more off

capture log close
log using "user_productivity_remote_eng_split.log", replace text

// Resolve data/results roots
capture confirm file "$processed_data/user_panel_precovid.dta"
if _rc {
    capture confirm file "data/processed/user_panel_precovid.dta"
    if !_rc {
        global processed_data "data/processed"
        global base_results  "results"
    }
    else {
        capture confirm file "../data/processed/user_panel_precovid.dta"
        if !_rc {
            global processed_data "../data/processed"
            global base_results  "../results"
        }
        else {
            global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
            global base_results  "/Users/saul/Dropbox/Remote Work Startups/main/results"
        }
    }
}

local specname "user_productivity_remote_eng_split"
local result_dir "$base_results/raw/`specname'"
cap mkdir "`result_dir'"

display "============================================================"
display "Remote × Post productivity by engineer composition"
display "Outcome: total contributions (percentile)"
display "Top tercile of 2019 engineer share = HighEng"
display "============================================================"

// ------------------------------------------------------------
// STEP 1: Load user panel and merge pre-COVID engineer shares
// ------------------------------------------------------------
use "$processed_data/user_panel_precovid.dta", clear

gen companyname_c = lower(companyname)

preserve
    use "$base_results/raw/composition_precovid_2019.dta", clear
    keep companyname_lower engineer_share_2019
    rename companyname_lower companyname_c
    tempfile comp
    save `comp'
restore

merge m:1 companyname_c using `comp', keep(match master)
keep if _merge == 3

// Define terciles of engineer share (pre-COVID, fixed)
xtile eng_tercile = engineer_share_2019, nq(3)

gen byte high_eng = (eng_tercile == 3)
label var high_eng "High engineer share (top tercile)"

gen byte low_eng = (eng_tercile <= 2)
label var low_eng "Low/mid engineer share"

drop eng_tercile

// Drop observations missing key variables
keep if !missing(var3, var4, var5, var6, var7, high_eng)

// ------------------------------------------------------------
// STEP 2: Build interaction terms for High/Low groups
// ------------------------------------------------------------

gen var3_high = var3 * high_eng
label var var3_high "Remote × Post × HighEng"

gen var3_low = var3 * low_eng
label var var3_low "Remote × Post × LowEng"

// Startup interaction split

gen var5_high = var5 * high_eng
label var var5_high "Remote × Post × Startup × HighEng"

gen var5_low = var5 * low_eng
label var var5_low "Remote × Post × Startup × LowEng"

// Instruments (WFH exposure × Post variants)

gen var6_high = var6 * high_eng

gen var6_low  = var6 * low_eng

gen var7_high = var7 * high_eng

gen var7_low  = var7 * low_eng

// ------------------------------------------------------------
// STEP 3: Set up result storage
// ------------------------------------------------------------
capture postclose handle
capture postclose handle_diff
capture postclose handle_fs

tempfile out
postfile handle ///
    str8  model_type ///
    str32 param ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

// Difference rows posted separately

tempfile out_diff
postfile handle_diff ///
    str8  model_type ///
    double coef se pval rkf nobs ///
    using `out_diff', replace

// First-stage summary

tempfile out_fs
postfile handle_fs ///
    str12 endovar ///
    str12 param ///
    double coef se pval partialF rkf nobs ///
    using `out_fs', replace

// Pre-COVID mean of outcome
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// Cluster id is user

// ------------------------------------------------------------
// STEP 4: OLS and IV regressions
// ------------------------------------------------------------

display _n "Running OLS (with High/Low splits)"
reghdfe total_contributions_q100 ///
    var3_high var3_low var5_high var5_low var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id)

local N = e(N)
foreach v in var3_high var3_low {
    local b  = _b[`v']
    local se = _se[`v']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("`v'") (`b') (`se') (`pv') (`pre_mean') (.) (`N')
}

// Difference (High - Low)
lincom var3_high - var3_low
post handle_diff ("OLS") (r(estimate)) (r(se)) (r(p)) (.) (`N')

// ------------------------------------------------------------
// IV specification with split instruments
// ------------------------------------------------------------
display _n "Running IV (with High/Low splits)"
ivreghdfe total_contributions_q100 ///
    (var3_high var3_low var5_high var5_low = ///
        var6_high var6_low var7_high var7_low) ///
    var4, absorb(user_id firm_id yh) vce(cluster user_id) savefirst

local rkf = e(rkf)
local N   = e(N)

foreach v in var3_high var3_low {
    local b  = _b[`v']
    local se = _se[`v']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("`v'") (`b') (`se') (`pv') (`pre_mean') (`rkf') (`N')
}

lincom var3_high - var3_low
post handle_diff ("IV") (r(estimate)) (r(se)) (r(p)) (`rkf') (`N')

// First-stage stats (report once)
matrix FS = e(first)
local F_v3h = FS[4,1]
local F_v3l = FS[4,2]
local F_v5h = FS[4,3]
local F_v5l = FS[4,4]
	estimates restore _ivreg2_var3_high
local N_fs = e(N)
foreach p in var6_high var6_low var7_high var7_low var4 {
    local b  = _b[`p']
    local se = _se[`p']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle_fs ("var3_high") ("`p'") (`b') (`se') (`pv') (`F_v3h') (`rkf') (`N_fs')
}
	estimates restore _ivreg2_var3_low
local N_fs = e(N)
foreach p in var6_high var6_low var7_high var7_low var4 {
    local b  = _b[`p']
    local se = _se[`p']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle_fs ("var3_low") ("`p'") (`b') (`se') (`pv') (`F_v3l') (`rkf') (`N_fs')
}
	estimates restore _ivreg2_var5_high
local N_fs = e(N)
foreach p in var6_high var6_low var7_high var7_low var4 {
    local b  = _b[`p']
    local se = _se[`p']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle_fs ("var5_high") ("`p'") (`b') (`se') (`pv') (`F_v5h') (`rkf') (`N_fs')
}
	estimates restore _ivreg2_var5_low
local N_fs = e(N)
foreach p in var6_high var6_low var7_high var7_low var4 {
    local b  = _b[`p']
    local se = _se[`p']
    local t  = `b'/`se'
    local pv = 2*ttail(e(df_r), abs(`t'))
    post handle_fs ("var5_low") ("`p'") (`b') (`se') (`pv') (`F_v5l') (`rkf') (`N_fs')
}

// ------------------------------------------------------------
// STEP 5: Export results
// ------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/coefficients.csv", ///
    replace delimiter(",") quote

postclose handle_diff
use `out_diff', clear
export delimited using "`result_dir'/differences.csv", ///
    replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
    replace delimiter(",") quote

capture log close
