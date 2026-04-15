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
*  Growth mechanisms analysis - following user_productivity_expost_growth_loop.do
*  Three specifications: baseline, endogenous growth, exogenous growth
*  Two FE types: firm#user and separate user/firm
*  Both OLS and IV for each
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* 1. Load main panel and merge firm controls
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

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

merge m:1 companyname_c using `firm_extra', keep(1 3) nogen
tempfile main_panel
save `main_panel'

*--------------------------------------------------------------------*
* 2. BASELINE SPECIFICATIONS (no growth interactions)
*--------------------------------------------------------------------*
di _n "=== BASELINE SPECIFICATIONS ==="

* Worker-Firm FE - OLS
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo baseline_ols_wf

* Worker-Firm FE - IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo baseline_iv_wf
estadd scalar rkf = e(rkf), replace

* Separate FE - OLS
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo baseline_ols_sep

* Separate FE - IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo baseline_iv_sep
estadd scalar rkf = e(rkf), replace

*--------------------------------------------------------------------*
* 3. ENDOGENOUS GROWTH (raw growth interactions)
*--------------------------------------------------------------------*
di _n "=== ENDOGENOUS GROWTH SPECIFICATIONS ==="

* Construct firm growth measures
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td
gen yh = hofd(date)
format yh %th
drop if date == 22797

collapse (last) total_employees date (sum) join leave, by(companyname yh)
gen byte covid = (yh >= 120)

* Average post-Covid growth
preserve
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    xtile tile_post_c = growth_rate_we_post_c, nq(2)
    tempfile g_postavg
    save `g_postavg'
restore

* Merge back to main panel
use `main_panel', clear
merge m:1 companyname using `g_postavg', keep(match) nogen

* Create endogenous growth interactions
gen var17 = covid*tile_post_c
gen var18 = covid*tile_post_c*startup

* Worker-Firm FE - OLS
reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo endog_ols_wf

* Worker-Firm FE - IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo endog_iv_wf
estadd scalar rkf = e(rkf), replace

* Separate FE - OLS
reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo endog_ols_sep

* Separate FE - IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo endog_iv_sep
estadd scalar rkf = e(rkf), replace

*--------------------------------------------------------------------*
* 4. EXOGENOUS GROWTH (residualized growth)
*--------------------------------------------------------------------*
di _n "=== EXOGENOUS GROWTH SPECIFICATIONS ==="

* Get firm keys for industry/MSA from user panel
preserve
    collapse (last) industry (last) company_msa, by(companyname)
    tempfile firmkeys
    save `firmkeys'
restore

* Reload growth data and compute leave-one-out means
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td
gen yh = hofd(date)
format yh %th
drop if date == 22797

collapse (last) total_employees date (sum) join leave, by(companyname yh)
gen byte covid = (yh >= 120)

merge m:1 companyname using `firmkeys', nogenerate
encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh
gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)
keep if covid
tempfile postcovid
save `postcovid'

* First collapse to firm-level average growth
use `postcovid', clear
collapse (mean) fg_we (first) industry company_msa, by(companyname)
rename fg_we firm_growth_avg
tempfile firm_growth
save `firm_growth'

* Industry leave-one-out at firm level
use `firm_growth', clear
bys industry: egen ind_sum = total(firm_growth_avg)
bys industry: egen ind_N = count(firm_growth_avg)
gen ind_growth_postavg_lo = (ind_sum - firm_growth_avg) / (ind_N - 1) if ind_N > 1
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

* MSA leave-one-out at firm level
use `firm_growth', clear
bys company_msa: egen msa_sum = total(firm_growth_avg)
bys company_msa: egen msa_N = count(firm_growth_avg)
gen msa_growth_postavg_lo = (msa_sum - firm_growth_avg) / (msa_N - 1) if msa_N > 1
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

* Merge everything and residualize growth - use firm-level data
use `firm_growth', clear
rename firm_growth_avg growth_rate_we_post_c
gen companyname_c = lower(companyname)
merge m:1 industry using `ind_postavg', keep(match) nogen
merge m:1 company_msa using `msa_postavg', keep(match) nogen
merge m:1 companyname_c using `firm_extra', keep(match) nogen

* First-stage growth residualization - now at true firm level
reghdfe growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi
eststo first_stage
predict growth_resid
xtile tile_growth_resid = growth_resid, nq(2)

* Keep firm-level measures
collapse (last) tile_growth_resid, by(companyname)
tempfile firm_measures
save `firm_measures'

* Merge back to main panel
use `main_panel', clear
merge m:1 companyname using `firm_measures', keep(match) nogen

* Create exogenous growth interactions
gen var17 = covid*tile_growth_resid
gen var18 = covid*tile_growth_resid*startup

* Worker-Firm FE - OLS
reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo exog_ols_wf

* Worker-Firm FE - IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo exog_iv_wf
estadd scalar rkf = e(rkf), replace

* Separate FE - OLS
reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo exog_ols_sep

* Separate FE - IV
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo exog_iv_sep
estadd scalar rkf = e(rkf), replace

*--------------------------------------------------------------------*
* 5. Export results to CSV for Python processing
*--------------------------------------------------------------------*
* Export coefficients to CSV for processing
eststo dir

preserve
    clear
    set obs 12
    
    gen spec_name = ""
    gen var3_coef = .
    gen var3_se = .
    gen var5_coef = .
    gen var5_se = .
    gen n_obs = .
    gen rkf = .
    
    local i = 1
    foreach spec in baseline_ols_wf baseline_iv_wf baseline_ols_sep baseline_iv_sep ///
                   endog_ols_wf endog_iv_wf endog_ols_sep endog_iv_sep ///
                   exog_ols_wf exog_iv_wf exog_ols_sep exog_iv_sep {
        
        qui estimates restore `spec'
        replace spec_name = "`spec'" in `i'
        replace var3_coef = _b[var3] in `i'
        replace var3_se = _se[var3] in `i'
        replace var5_coef = _b[var5] in `i'
        replace var5_se = _se[var5] in `i'
        replace n_obs = e(N) in `i'
        cap replace rkf = e(rkf) in `i'
        
        local i = `i' + 1
    }
    
    export delimited using "$clean_results/growth_mechanisms_results.csv", replace
restore

* Also export first-stage results
estimates restore first_stage
esttab first_stage using "$clean_results/growth_first_stage.csv", ///
    cells(b(fmt(3)) se(fmt(3))) ///
    stats(N r2) ///
    csv replace

di _n "=== ANALYSIS COMPLETE ==="
di "Results exported to:"
di "  - $clean_results/growth_mechanisms_results.csv"
di "  - $clean_results/growth_first_stage.csv"