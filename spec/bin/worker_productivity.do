*----------------------------------------------------------
* 1) Set Global Variables, Specification Name, and Paths
*----------------------------------------------------------
do "../src/globals.do"

local specname   "worker_productivity"
local result_path "$results/`specname'"
capture mkdir "`result_path'"

use "$processed_data/worker_panel.dta", clear

local outcomes total_contributions_q100 restricted_contributions_q100

foreach outcome of local outcomes {
    
    di as text "Processing outcome: `outcome'"
    
    ********************************************************
    * OLS Regression: Report Only Pre-COVID Mean
    ********************************************************
    reghdfe `outcome' var3 var5 var4, ///
        absorb(user_id firm_id yh) ///
        vce(cluster user_id)
    
    * Calculate the pre-COVID mean using observations with covid == 0
    quietly summarize `outcome' if e(sample) & covid == 0
    local precovid_mean = r(mean)
    
    outreg2 using "`result_path'/ols_`outcome'.tex", ///
        tex replace ///
        addstat("Pre-COVID Y-Mean", `precovid_mean')
    
    ********************************************************
    * IV Regression (2SLS): Report Only Pre-COVID Mean & RFK F Stat
    ********************************************************
    ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
        absorb(user_id firm_id yh) ///
        vce(cluster user_id) ///
        savefirst
    
    quietly summarize `outcome' if e(sample) & covid == 0
    local precovid_mean = r(mean)
	local rkf = e(rkf)
    
    outreg2 using "`result_path'/iv_`outcome'.tex", ///
        tex replace ///
        addstat("Pre-COVID Y-Mean", `precovid_mean', ///
                "KP rk Wald F", `rkf')
    
    ********************************************************
    * Extract and Save First Stage Partial F Statistics
    ********************************************************
    matrix FS = e(first)
    local partialF_3 = FS[4,1]
    local partialF_5 = FS[4,2]
    
    estimates restore _ivreg2_var3
    outreg2 using "`result_path'/fs_`outcome'_var3.tex", ///
        tex replace ///
        addstat("Partial F(var3)", `partialF_3', ///
		`'"KP rk Wald F", `rkf')
		
    
    estimates restore _ivreg2_var5
    outreg2 using "`result_path'/fs_`outcome'_var5.tex", ///
        tex replace ///
        addstat("Partial F(var5)", `partialF_5', ///
		"KP rk Wald F", `rkf')
		
}
