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



*====================================================================*
*  spec/growth_mechanisms_corrected.do
*  ------------------------------------------------------------------
*  Corrected to use fitted values (not residuals) for exogenous growth
*  Tests baseline, endogenous (raw), and exogenous (fitted) growth
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

local specname "growth_mechanisms_corrected_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

*--------------------------------------------------------------------*
* 1. Load main panel
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

*--------------------------------------------------------------------*
* 2. Get firm controls (matching original script)
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi = hhi_1000, nq(2)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen

tempfile main_panel
save `main_panel'

*--------------------------------------------------------------------*
* 3. Construct firm growth measures (matching original)
*--------------------------------------------------------------------*
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
format yh %th

* Drop June 2022 outliers
drop if date == 22797

* Collapse to firm-half-year
collapse (last) total_employees date (sum) join leave, by(companyname yh)

gen byte covid = (yh >= 120)

* Calculate average post-COVID growth rate
preserve
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    
    * Create ENDOGENOUS growth tile (raw)
    xtile tile_post_c = growth_rate_we_post_c, nq(2)
    
    tempfile g_postavg
    save `g_postavg'
restore

*--------------------------------------------------------------------*
* 4. Get industry and MSA keys for residualization
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname industry
    * Create placeholder MSA since variable doesn't exist
    gen company_msa = "all"
    bysort companyname: keep if _n == 1
    tempfile firmkeys
    save `firmkeys'
restore

*--------------------------------------------------------------------*
* 5. Calculate leave-one-out growth measures (matching original)
*--------------------------------------------------------------------*
merge m:1 companyname using `firmkeys', nogenerate

encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh

gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)

keep if covid  // post-COVID only
tempfile postcovid
save `postcovid'

* Industry leave-one-out mean
use `postcovid', clear
bys industry: egen ind_sum = total(fg_we)
bys industry: egen ind_N = count(fg_we)
gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

* MSA leave-one-out mean
use `postcovid', clear
bys company_msa: egen msa_sum = total(fg_we)
bys company_msa: egen msa_N = count(fg_we)
gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
keep company_msa msa_growth_postavg_lo
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

*--------------------------------------------------------------------*
* 6. Create EXOGENOUS growth (using FITTED VALUES, not residuals!)
*--------------------------------------------------------------------*
use `postcovid', clear
gen companyname_c = lower(companyname)

merge m:1 industry using `ind_postavg', keep(match) nogen
merge m:1 company_msa using `msa_postavg', keep(match) nogen
merge m:1 companyname using `g_postavg', keep(match) nogen
merge m:1 companyname_c using `firm_extra', keep(match) nogen

* This matches line 281 of original script
reg growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi

* IMPORTANT: Use fitted values (predicted growth), NOT residuals!
predict growth_fitted
* This is the growth explained by industry/MSA/rent/HHI - i.e., exogenous factors

* Create EXOGENOUS growth tile (fitted/predicted values)
xtile tile_growth_exog = growth_fitted, nq(2)

collapse (last) tile_growth_exog (last) tile_post_c, by(companyname)

tempfile firm_measures
save `firm_measures'

*--------------------------------------------------------------------*
* 7. Merge back to main panel and create interactions
*--------------------------------------------------------------------*
use `main_panel', clear
merge m:1 companyname using `firm_measures', keep(match) nogen

* Endogenous growth interactions (raw)
gen var17 = covid * tile_post_c
gen var18 = covid * tile_post_c * startup

* Exogenous growth interactions (fitted values)
gen var19 = covid * tile_growth_exog
gen var20 = covid * tile_growth_exog * startup

*--------------------------------------------------------------------*
* 8. Setup postfile
*--------------------------------------------------------------------*
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  /// 
    str40  spec        ///
    str10  param       ///
    double coef se pval pre_mean rkf nobs /// 
    using `out', replace

*--------------------------------------------------------------------*
* 9. Pre-COVID mean
*--------------------------------------------------------------------*
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

*--------------------------------------------------------------------*
* 10. Run three specifications
*--------------------------------------------------------------------*

* Specification 1: Baseline
di "Running baseline specification..."

reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("baseline") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("baseline") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 2: Endogenous Growth (raw tiles)
di "Running endogenous growth specification..."

reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("endo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("endo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

* Specification 3: Exogenous Growth (fitted values)
di "Running exogenous growth specification..."

reghdfe total_contributions_q100 var3 var5 var4 var19 var20, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
local N = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("OLS") ("exo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (.) (`N')
}

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var19 var20, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
local rkf = e(rkf)
local N   = e(N)
foreach p in var3 var5 {
    local b    = _b[`p']
    local se   = _se[`p']
    local t    = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("IV") ("exo_growth") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') ///
                (`rkf') (`N')
}

*--------------------------------------------------------------------*
* 11. Save results
*--------------------------------------------------------------------*
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace

di as result "Results saved to `result_dir'/consolidated_results.csv"

log close
