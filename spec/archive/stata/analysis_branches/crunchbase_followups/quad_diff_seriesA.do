*============================================================*
* quad_diff_seriesA.do
* Quadruple-difference: Remote x Post x Startup x Series A+ (pre-2020)
* - Builds Series A+ flag from Crunchbase funding_rounds
* - Runs OLS and IV (teleworkable instruments) with firm and half-year FE
* - Exports consolidated_results.csv for downstream TeX table
*============================================================*

// 0) Setup
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
do "`__bootstrap'"

local specname quad_diff_seriesA
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

local result_dir "$results/`specname'"
local cb_funding "$raw_data/crunchbase/funding_rounds.csv"
cap mkdir "`result_dir'"

// 1) Load panel
capture confirm file "$processed_data/firm_panel_with_cb.csv"
if _rc {
    di as error "Missing panel input: $processed_data/firm_panel_with_cb.csv"
    di as error "Rebuild the firm panel (and Crunchbase crosswalk) before running `specname'."
    exit 601
}
import delimited using "$processed_data/firm_panel_with_cb.csv", clear stringcols(_all)

// numeric conversions
foreach v in remote teleworkable covid startup growth_rate_we leave_rate_we join_rate_we total_employees anyremote hybrid fullrem inperson nonrem var3 var4 var5 var6 var7 var3_anyremote var5_anyremote {
    capture confirm numeric variable `v'
    if _rc destring `v', replace ignore(" .,-")
}

capture confirm numeric variable firm_id
if _rc {
    encode firm_id, gen(firm_id_num)
}
else {
    gen firm_id_num = firm_id
}

// rebuild treatment bundle
foreach v in var3 var4 var5 var6 var7 var3_vc var4_vc var5_vc var6_vc var7_vc anyremote {
    capture drop `v'
}
clonevar anyremote = remote
replace anyremote = anyremote > 0 if !missing(anyremote)
replace anyremote = 0 if missing(anyremote)

gen double var3 = anyremote * covid
label var var3 "remote x covid"
gen double var5 = anyremote * covid * startup
label var var5 "remote x covid x startup"
gen double var4 = covid * startup
label var var4 "covid x startup"
gen double var6 = covid * teleworkable
label var var6 "covid x teleworkable"
gen double var7 = startup * covid * teleworkable
label var var7 "startup x covid x teleworkable"

// 2) Series A+ pre-2020 flag from Crunchbase
capture confirm file "`cb_funding'"
if _rc {
    di as error "Missing Crunchbase funding rounds: `cb_funding'"
    di as error "Place the file under data/raw/crunchbase/funding_rounds.csv (untracked)."
    exit 601
}
preserve
    import delimited using "`cb_funding'", clear stringcols(_all)
    keep org_uuid announced_on investment_type
    gen str30 it = lower(investment_type)
    gen double ann = daily(announced_on, "YMD")
    gen byte series_plus = regexm(it, "^series_[a-i]") | inlist(it, "venture_round", "growth_equity", "private_equity", "series_unknown")
    keep if series_plus == 1
    collapse (min) first_series = ann, by(org_uuid)
    gen byte vc_series_pre2020 = !missing(first_series) & first_series <= daily("2019-12-31","YMD")
    tempfile vc_temp
    save `vc_temp'
restore

merge m:1 org_uuid using `vc_temp', keep(master match) nogen
replace vc_series_pre2020 = 0 if missing(vc_series_pre2020)

local vcvar vc_series_pre2020
foreach t in 3 4 5 6 7 {
    gen double var`t'_vc = var`t' * `vcvar'
}

// 3) Postfile for results
capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str20 param ///
    double coef se pval rkf nobs ///
    using `out', replace

// 4) OLS
reghdfe growth_rate_we var3 var5 var4 var3_vc var5_vc var4_vc, absorb(firm_id_num yh) vce(cluster firm_id_num)
local N = e(N)
foreach p in var3 var5 var4 var3_vc var5_vc var4_vc {
    local b = _b[`p']
    local se = _se[`p']
    local t = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("`p'") (`b') (`se') (`pval') (.) (`N')
}

// 5) IV
ivreghdfe growth_rate_we (var3 var5 var3_vc var5_vc = var6 var7 var6_vc var7_vc) var4 var4_vc, absorb(firm_id_num yh) vce(cluster firm_id_num) first
local N = e(N)
local rkf = e(rkf)
foreach p in var3 var5 var4 var3_vc var5_vc var4_vc {
    local b = _b[`p']
    local se = _se[`p']
    local t = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("`p'") (`b') (`se') (`pval') (`rkf') (`N')
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

di as result "→ Wrote `result_dir'/consolidated_results.csv"

log close _all
