*============================================================*
* do/user_mechanisms_regressions.do
*  — Automated export of OLS, IV & first-stage F's
*    across 8 specification columns
*============================================================*

capture log close
cap mkdir "log"
// Canonical user mechanism regression script (wage included by default)
*---------------------------------------------------------------------------*
* 0) Parse optional panel variant argument ----------------------------------
*     Accepts:  unbalanced | balanced | precovid  (default = precovid)
*---------------------------------------------------------------------------*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

*---------------------------------------------------------------------------*
* Ensure the panel variant is explicitly part of every identifier so that
* results can never be mistaken for a different sample.
*---------------------------------------------------------------------------*

local specname   "user_mechanisms_lean_`panel_variant'"
log using "log/`specname'.log", replace text


// 1) Globals + setup
do "../src/globals.do"
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

// 1) Load & prepare once
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen seniority_4 = !inrange(seniority_levels,1,3)





preserve


args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"


use "$processed_data/user_panel_`panel_variant'.dta", clear
collapse (last) industry (last) company_msa (last) hqcity (last) hqstate, by(companyname)
keep companyname industry company_msa
tempfile industries
save `industries', replace



import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th


drop if date == 22797
gen byte covid = yh >= 120     

merge m:1 companyname using `industries', nogenerate   



collapse (last) total_employees date (sum) join leave (last) covid, by(yh industry)



encode companyname, gen(company_numeric)
xtset company_numeric yh
// sort company_numeric yh

encode industry, gen(industry_numeric)
xtset industry_numeric yh
sort industry_numeric yh

gen growth_rate = (total_employees / L.total_employees) - 1 if _n > 1


winsor2 growth_rate, cuts(1 99) suffix(_we)
drop growth_rate

collapse growth_rate_we, by(industry covid)
drop if covid == 0

rename growth_rate_we growth_rate_we_ind
drop covid 

tempfile industry_growth
save `industry_growth', replace



import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
gen year = yofd(date)
format yh %th


drop if date == 22797
gen byte covid = yh >= 120     




collapse (last) total_employees date (sum) join leave (last) covid, by(yh companyname)



encode companyname, gen(company_numeric)
xtset company_numeric yh
sort company_numeric yh



gen growth_rate = (total_employees / L.total_employees) - 1 if _n > 1


winsor2 growth_rate, cuts(1 99) suffix(_we)
drop growth_rate

collapse growth_rate_we, by(companyname covid)
drop if covid == 0

rename growth_rate_we growth_rate_we_post_c

drop covid 

merge m:1 companyname using `industries', nogenerate   

tempfile company_post_growth
save `company_post_growth', replace



merge m:1 industry using `industry_growth'
drop if industry == ""


bysort company_msa : egen avg_msa = mean(growth_rate_we_post_c)
bysort industry : egen avg_ind = mean(growth_rate_we_post_c)

regress growth_rate_we_post_c avg_ind avg_msa

predict yhat
sum yhat

xtile lg_tile = yhat, nq(2)



tempfile firm_growth          // temp filename macro
save `firm_growth', replace   // dataset lives only this session


restore



merge m:1 companyname using `firm_growth', nogenerate   




gen var17 = covid*lg_tile
gen var18 = covid*lg_tile*startup


// ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
//     absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
	
ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
    absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
	
	



// interactions
gen var8  = covid*rent
gen var9 = covid*rent*startup
// gen var11  = covid*hhi_1000
// gen var12 = covid*hhi_1000*startup
gen var11  = covid*lg_tile
gen var12 = covid*lg_tile*startup
// gen var14  = covid*seniority_4
// gen var15 = covid*seniority_4*startup

gen var14  = covid*emp_pre
gen var15 = covid*emp_pre*startup


// pick your mechanism here
// local mech    sd_wage
// local mech_label  sdw 

local mech    p90_p10_gap
local mech_label  gap

gen p90_p10_gap = 1
// generate interactions
gen var17 = covid*`mech'
gen var18 = covid*`mech'*startup





capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  /// 
    str244 spec        ///
    str40  param       ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace



local specs ///
  "baseline" ///
  "rent" "hhi" "seniority" "`mech_label'" ///
  "rent_hhi" "rent_seniority" "rent_`mech_label'" "hhi_seniority" "hhi_`mech_label'" "seniority_`mech_label'" ///
  "rent_hhi_seniority" "rent_hhi_`mech_label'" "rent_seniority_`mech_label'" "hhi_seniority_`mech_label'" ///
  "rent_hhi_seniority_`mech_label'"


  
* ────────────────────────────────────────────────────────
* 3) Define spec_… locals for OLS exog, IV exog, instruments & endogenous
*    (indices correspond to word positions in `specs`)
* ────────────────────────────────────────────────────────

//  1) baseline
local spec_ols_exog1  var4
local spec_iv_exog1   var4
local spec_instr1     var6 var7
local spec_endo1      var3 var5

//  2) rent
local spec_ols_exog2  var4 var8 var9  
local spec_iv_exog2   var4 var8 var9
local spec_instr2     var6 var7 
local spec_endo2      var3 var5 

//  3) hhi
local spec_ols_exog3  var4 var11 var12 
local spec_iv_exog3   var4 var11 var12
local spec_instr3     var6 var7 
local spec_endo3      var3 var5 

//  4) seniority
local spec_ols_exog4  var4 var14 var15 
local spec_iv_exog4   var4 var14 var15
local spec_instr4     var6 var7 
local spec_endo4      var3 var5 

//  5) `mech'
local spec_ols_exog5  var4 var17 var18 
local spec_iv_exog5   var4 var17 var18
local spec_instr5     var6 var7 
local spec_endo5      var3 var5 

//  6) rent_hhi
local spec_ols_exog6  var4 var8 var9  var11 var12 
local spec_iv_exog6   var4 var8 var9 var11 var12
local spec_instr6     var6 var7  
local spec_endo6      var3 var5  

//  7) rent_seniority
local spec_ols_exog7  var4 var8 var9  var14 var15 
local spec_iv_exog7   var4 var8 var9 var14 var15
local spec_instr7     var6 var7  
local spec_endo7      var3 var5  

//  8) rent_`mech'
local spec_ols_exog8  var4 var8 var9  var17 var18 
local spec_iv_exog8   var4 var8 var9 var17 var18
local spec_instr8     var6 var7  
local spec_endo8      var3 var5  

//  9) hhi_seniority
local spec_ols_exog9  var4 var11 var12  var14 var15 
local spec_iv_exog9   var4 var11 var12 var14 var15
local spec_instr9     var6 var7  
local spec_endo9      var3 var5  

// 10) hhi_`mech'
local spec_ols_exog10 var4 var11 var12  var17 var18 
local spec_iv_exog10  var4 var11 var12 var17 var18
local spec_instr10    var6 var7  
local spec_endo10     var3 var5  

// 11) `mech'_seniority
local spec_ols_exog11 var4 var17 var18  var14 var15 
local spec_iv_exog11  var4 var17 var18 var14 var15
local spec_instr11    var6 var7  
local spec_endo11     var3 var5  

// 12) rent_hhi_seniority
local spec_ols_exog12 var4 var8 var9  var11 var12  var14 var15 
local spec_iv_exog12  var4 var8 var9 var11 var12 var14 var15
local spec_instr12    var6 var7   
local spec_endo12     var3 var5   

// 13) rent_hhi_`mech'
local spec_ols_exog13 var4 var8 var9  var11 var12  var17 var18 
local spec_iv_exog13  var4 var8 var9 var11 var12 var17 var18
local spec_instr13    var6 var7   
local spec_endo13     var3 var5   

// 14) rent_seniority_`mech'
local spec_ols_exog14 var4 var8 var9  var14 var15  var17 var18 
local spec_iv_exog14  var4 var8 var9 var14 var15 var17 var18
local spec_instr14    var6 var7   
local spec_endo14     var3 var5   

// 15) hhi_seniority_`mech'
local spec_ols_exog15 var4 var11 var12  var14 var15  var17 var18 
local spec_iv_exog15  var4 var11 var12 var14 var15 var17 var18
local spec_instr15    var6 var7   
local spec_endo15     var3 var5   

// 16) rent_hhi_seniority_`mech'
local spec_ols_exog16 var4 var8 var9  var11 var12  var14 var15  var17 var18 
local spec_iv_exog16  var4 var8 var9 var11 var12 var14 var15 var17 var18
local spec_instr16    var6 var7    
local spec_endo16     var3 var5    



// drop if missing(rent, hhi_1000, seniority_4, sd_wage, p90_p10_gap)


// 3) SPEC 1: Baseline on the full sample
display as text "→ Spec 1: baseline (full sample)"

summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// 3a) OLS
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

// 3b) IV
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



// 4) Loop
forvalues i = 2/8 {
    // 1) pick the spec name
    local spec    : word `i' of `specs'

    // 2) build up the four pieces we need
    local ols_exog "`spec_ols_exog`i''"
    local iv_exog  "`spec_iv_exog`i''"
    local instr    "`spec_instr`i''"
    local endo     "`spec_endo`i''"
	

    display as text "→ Spec `i': `spec'"

    summarize total_contributions_q100 if covid == 0, meanonly
    local pre_mean = r(mean)

    // 4a) OLS
    reghdfe total_contributions_q100 var3 var5 `ols_exog', ///
        absorb(firm_id#user_id yh) vce(cluster user_id)
	
	local N = e(N) 
	
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
       post handle ("OLS") ("`spec'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (.) (`N')
    }

    // 4b) IV
    ivreghdfe total_contributions_q100 (`endo' = `instr') `iv_exog', ///
        absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
    local rkf = e(rkf)
	local N   = e(N)
	
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
       post handle ("IV") ("`spec'") ("`p'") ///
                    (`b') (`se') (`pval') (`pre_mean') ///
                    (`rkf') (`N')
    }

}

// 5) Close & export
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

display as result "→ CSV written to `result_dir'/consolidated_results.csv"
capture log close
