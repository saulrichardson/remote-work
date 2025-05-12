do "../src/globals.do"

* Local specification name
local specname "firm_mechanisms"
local result_path "$results/`specname'"
capture mkdir "`result_path'"


use "$processed_data/firm_panel", clear

gen seniority_4 = !inrange(seniority_levels, 1 ,3)
drop if missing(hhi_1000, seniority_4, rent)


* Define Rent-related Interactions
gen var8 = covid * rent               
gen var9 = covid * rent * remote       
gen var10 = teleworkable * covid * rent  

* Define HHI-based Centrality Interactions
gen var11 = covid * hhi_1000              
gen var12 = covid * hhi_1000 * remote     
gen var13 = teleworkable * covid * hhi_1000 

* Define Seniority-based Interactions 
gen var14 = covid * seniority_4              
gen var15 = covid * seniority_4 * remote     
gen var16 = teleworkable * covid * seniority_4 

* Define Seniority-based Interactions 
gen var14 = covid * seniority_4              
gen var15 = covid * seniority_4 * remote     
gen var16 = teleworkable * covid * seniority_4 



* Column 1: Baseline only
reghdfe growth_rate_we ///
    var3 var4 var5, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", replace ///
    ctitle("Col 1: Baseline") tex ///
    keep(var3 var5)

* Column 2: Baseline + Rent interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var8 var9, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 2: + Rent") tex ///
    keep(var3 var5)

* Column 3: Baseline + HHI-based Centrality interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var11 var12, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 3: + HHI") tex ///
    keep(var3 var5)

* Column 4: Baseline + Both Rent + HHI-based Centrality interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var8 var9 var11 var12, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 4: + Rent + HHI") tex ///
    keep(var3 var5)

* Column 5: Baseline + Seniority interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var14 var15, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 5: + Seniority") tex ///
    keep(var3 var5)

* Column 6: Baseline + Rent + Seniority interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var8 var9 var14 var15, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 6: + Rent + Seniority") tex ///
    keep(var3 var5)

* Column 7: Baseline + HHI + Seniority interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var11 var12 var14 var15, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 7: + HHI + Seniority") tex ///
    keep(var3 var5)

* Column 8: Baseline + Rent + HHI + Seniority interactions
reghdfe growth_rate_we ///
    var3 var4 var5 var8 var9 var11 var12 var14 var15, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/OLS_results_firm.tex", append ///
    ctitle("Col 8: + Rent, HHI + Seniority") tex ///
    keep(var3 var5)

*************************************************************************
* Panel B: IV Specifications (Firm Level)
*************************************************************************
* For IV, note:
*  - In the baseline IV, (var3, var5) are instrumented by (var6, var7) and controlled by var4.
*  - With additional interactions:
*      • Rent: add endogenous var9 with instrument var10 and exog var8.
*      • HHI-based Centrality: add endogenous var12 with instrument var13 and exog var11.
*      • Seniority: add endogenous var15 with instrument var16 and exog var14.
*************************************************************************

* Column 1: Baseline IV only
ivreghdfe growth_rate_we ///
    (var3 var5 = var6 var7) var4, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", replace ///
    ctitle("Col 1: Baseline") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 2: Baseline + Rent interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var9 = var6 var7 var10) ///
    var4 var8, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 2: + Rent") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 3: Baseline + HHI-based Centrality interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var12 = var6 var7 var13) ///
    var4 var11, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 3: + HHI") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 4: Baseline + Rent + HHI interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var9 var12 = var6 var7 var10 var13) ///
    var4 var8 var11, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 4: + Rent + HHI") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 5: Baseline + Seniority interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var15 = var6 var7 var16) ///
    var4 var14, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 5: + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 6: Baseline + Rent + Seniority interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var9 var15 = var6 var7 var10 var16) ///
    var4 var8 var14, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 6: + Rent + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 7: Baseline + HHI + Seniority interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var12 var15 = var6 var7 var13 var16) ///
    var4 var11 var14, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 7: + HHI + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

* Column 8: Baseline + Rent + HHI + Seniority interactions IV
ivreghdfe growth_rate_we ///
    (var3 var5 var9 var12 var15 = var6 var7 var10 var13 var16) ///
    var4 var8 var11 var14, ///
    absorb(firm_id yh) ///
    vce(cluster firm_id)
outreg2 using "`result_path'/IV_results_firm.tex", append ///
    ctitle("Col 8: + Rent, HHI + Seniority") tex ///
    keep(var3 var5) addstat("KP rk Wald F", e(rkf))

