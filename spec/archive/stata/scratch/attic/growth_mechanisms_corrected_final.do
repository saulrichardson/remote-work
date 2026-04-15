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
*  Growth mechanisms analysis with correct specifications
*  Properly interacts instruments with growth indicators
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* 1. Load main user panel data
*--------------------------------------------------------------------*
use "$processed_data/user_panel_`panel_variant'.dta", clear
count
di "Initial observations: " r(N)

*--------------------------------------------------------------------*
* 2. Get firm controls with RELAXED merge for baseline
*--------------------------------------------------------------------*
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    tempfile firm_extra
    save `firm_extra'
restore

gen companyname_c = lower(companyname)

* RELAXED MERGE - keep all observations for baseline
merge m:1 companyname_c using `firm_extra', keep(1 3) nogen

* Flag observations with growth controls
gen has_growth_controls = !missing(rent, hhi_1000)
count
di "After relaxed merge: " r(N)
count if has_growth_controls
di "Observations with growth controls: " r(N)

tempfile main_panel
save `main_panel'

*--------------------------------------------------------------------*
* 3. BASELINE REGRESSIONS WITH ALL OBSERVATIONS
*--------------------------------------------------------------------*
di _n "=== BASELINE REGRESSIONS ==="

* OLS with separate FEs
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo ols_baseline_sep
estadd scalar n_obs = e(N)

* IV with separate FEs
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo iv_baseline_sep
estadd scalar rkf = e(rkf), replace
estadd scalar n_obs = e(N)

* OLS with worker-firm FEs
reghdfe total_contributions_q100 var3 var5 var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo ols_baseline_wf
estadd scalar n_obs = e(N)

* IV with worker-firm FEs
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo iv_baseline_wf
estadd scalar rkf = e(rkf), replace
estadd scalar n_obs = e(N)

*--------------------------------------------------------------------*
* 4. CONSTRUCT GROWTH MEASURES
*--------------------------------------------------------------------*
* Now work with subset that has growth controls
preserve
keep if has_growth_controls

* Get firm growth data
preserve
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
    
    * Calculate growth rates
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

* Get firm industry/MSA keys
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname industry
    gen company_msa = "all"
    bysort companyname: keep if _n == 1
    tempfile firmkeys
    save `firmkeys'
restore

* Build leave-one-out growth rates
preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi = hhi_1000, nq(2)
    tempfile firm_extra2
    save `firm_extra2'
restore

preserve
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
    
    * Industry leave-one-out
    use `postcovid', clear
    bys industry: egen ind_sum = total(fg_we)
    bys industry: egen ind_N = count(fg_we)
    gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
    collapse (mean) ind_growth_postavg_lo, by(industry)
    tempfile ind_postavg
    save `ind_postavg'
    
    * MSA leave-one-out (placeholder)
    use `postcovid', clear
    bys company_msa: egen msa_sum = total(fg_we)
    bys company_msa: egen msa_N = count(fg_we)
    gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
    keep company_msa msa_growth_postavg_lo
    collapse (mean) msa_growth_postavg_lo, by(company_msa)
    tempfile msa_postavg
    save `msa_postavg'
    
    * Merge and run residualization
    use `postcovid', clear
    gen companyname_c = lower(companyname)
    merge m:1 industry using `ind_postavg', keep(match) nogen
    merge m:1 company_msa using `msa_postavg', keep(match) nogen
    merge m:1 companyname using `g_postavg', keep(match) nogen
    merge m:1 companyname_c using `firm_extra2', keep(match) nogen
    
    * First-stage regression for growth residualization
    reg growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi
    eststo first_stage
    predict growth_resid
    
    * Create EXOGENOUS growth tile (fitted values)
    xtile tile_growth_resid = growth_resid, nq(2)
    
    * Keep only firm-level growth info
    keep companyname tile_post_c tile_growth_resid
    duplicates drop
    tempfile growth_tiles
    save `growth_tiles'
restore

* Merge growth back to user panel
merge m:1 companyname using `growth_tiles', keep(match) nogen

* Create growth indicators
gen high_growth_post = (tile_post_c == 2)
gen high_growth_resid = (tile_growth_resid == 2)

*--------------------------------------------------------------------*
* 5. ENDOGENOUS GROWTH SPECIFICATIONS
*--------------------------------------------------------------------*
di _n "=== ENDOGENOUS GROWTH SPECIFICATIONS ==="

* Create interactions for endogenous growth
gen var3_growth = var3 * high_growth_post
gen var5_growth = var5 * high_growth_post
gen var6_growth = var6 * high_growth_post
gen var7_growth = var7 * high_growth_post

* OLS with separate FEs
reghdfe total_contributions_q100 var3 var5 var4 var3_growth var5_growth high_growth_post, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo ols_endog_sep
estadd scalar n_obs = e(N)

* IV with separate FEs
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo iv_endog_sep
estadd scalar rkf = e(rkf), replace
estadd scalar n_obs = e(N)

* OLS with worker-firm FEs
reghdfe total_contributions_q100 var3 var5 var4 var3_growth var5_growth high_growth_post, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo ols_endog_wf
estadd scalar n_obs = e(N)

* IV with worker-firm FEs
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_growth var5_growth = var6 var7 var6_growth var7_growth) ///
    var4 high_growth_post, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo iv_endog_wf
estadd scalar rkf = e(rkf), replace
estadd scalar n_obs = e(N)

drop var3_growth var5_growth var6_growth var7_growth

*--------------------------------------------------------------------*
* 6. EXOGENOUS GROWTH SPECIFICATIONS
*--------------------------------------------------------------------*
di _n "=== EXOGENOUS GROWTH SPECIFICATIONS ==="

* Create interactions for exogenous growth
gen var3_gresid = var3 * high_growth_resid
gen var5_gresid = var5 * high_growth_resid
gen var6_gresid = var6 * high_growth_resid
gen var7_gresid = var7 * high_growth_resid

* OLS with separate FEs
reghdfe total_contributions_q100 var3 var5 var4 var3_gresid var5_gresid high_growth_resid, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo ols_exog_sep
estadd scalar n_obs = e(N)

* IV with separate FEs
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_gresid var5_gresid = var6 var7 var6_gresid var7_gresid) ///
    var4 high_growth_resid, ///
    absorb(user_id firm_id yh) vce(cluster user_id)
eststo iv_exog_sep
estadd scalar rkf = e(rkf), replace
estadd scalar n_obs = e(N)

* OLS with worker-firm FEs
reghdfe total_contributions_q100 var3 var5 var4 var3_gresid var5_gresid high_growth_resid, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo ols_exog_wf
estadd scalar n_obs = e(N)

* IV with worker-firm FEs
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_gresid var5_gresid = var6 var7 var6_gresid var7_gresid) ///
    var4 high_growth_resid, ///
    absorb(firm_id#user_id yh) vce(cluster user_id)
eststo iv_exog_wf
estadd scalar rkf = e(rkf), replace
estadd scalar n_obs = e(N)

restore

*--------------------------------------------------------------------*
* 7. Export results
*--------------------------------------------------------------------*
* Export first-stage
esttab first_stage using "$clean_results/growth_first_stage.tex", ///
    replace booktabs label ///
    title("First-Stage Regression: Firm Growth Residualization") ///
    b(3) se(3) ///
    stats(N r2, fmt(%9.0fc %9.3f) labels("Observations" "R-squared")) ///
    mtitles("Firm Growth Rate") ///
    note("Growth rate is average post-COVID employment growth.")

* Export separate FE results
esttab ols_baseline_sep iv_baseline_sep ols_endog_sep iv_endog_sep ols_exog_sep iv_exog_sep ///
    using "$clean_results/growth_mechanisms_separate_fe.tex", ///
    replace booktabs label ///
    title("Remote Work Effects: Separate Fixed Effects") ///
    b(2) se(2) ///
    keep(var3 var5) ///
    varlabels(var3 "Remote × Post" var5 "Remote × Post × Startup") ///
    stats(n_obs rkf, fmt(%9.0fc %9.1f) labels("Observations" "KP rk Wald F")) ///
    mtitles("OLS Base" "IV Base" "OLS Endog" "IV Endog" "OLS Exog" "IV Exog") ///
    note("Standard errors clustered by user. * p<0.10, ** p<0.05, *** p<0.01")

* Export worker-firm FE results
esttab ols_baseline_wf iv_baseline_wf ols_endog_wf iv_endog_wf ols_exog_wf iv_exog_wf ///
    using "$clean_results/growth_mechanisms_workerfirm_fe.tex", ///
    replace booktabs label ///
    title("Remote Work Effects: Worker-Firm Fixed Effects") ///
    b(2) se(2) ///
    keep(var3 var5) ///
    varlabels(var3 "Remote × Post" var5 "Remote × Post × Startup") ///
    stats(n_obs rkf, fmt(%9.0fc %9.1f) labels("Observations" "KP rk Wald F")) ///
    mtitles("OLS Base" "IV Base" "OLS Endog" "IV Endog" "OLS Exog" "IV Exog") ///
    note("Standard errors clustered by user. * p<0.10, ** p<0.05, *** p<0.01")

log close