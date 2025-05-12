* 0) Setup environment
do "../src/globals.do"

* 1) Load firm-level master data
use "$processed_data/firm_panel.dta", clear

* 2) Set up output directories
local specname "firm_scaling"
local result_path "$results/`specname'"
capture mkdir "`result_path'"

// Lock in file names (panel_suffix is "min"):
local ols_file  "`result_path'/ols.tex"
local iv_file   "`result_path'/iv.tex"
local fs_file   "`result_path'/first_stage.tex"

// Initialize counters for file writing:
local first_ols   1
local first_iv    1
local fs_done   0        


// Define outcome variables
local outcome_vars growth_rate_we join_rate_we leave_rate_we

// Loop over each outcome variable:
foreach outcome of local outcome_vars {
    
    di as text "Processing outcome: `outcome'"
    
    //----- OLS Regression -----
    reghdfe `outcome' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id) 
    
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
        absorb(firm_id yh) vce(cluster firm_id)  savefirst
    
    // Compute pre-COVID mean for IV sample:
    quietly summarize `outcome' if e(sample) & covid == 0
    local precovid_mean = r(mean)
	local rkf = e(rkf)
    
    // Write IV results, reporting only the RFK F statistic along with the pre-COVID mean:
    if `first_iv' == 1 {
        outreg2 using "`iv_file'", tex(frag) replace ///
            addstat("Pre-COVID Y-Mean", `precovid_mean', ///
                    "K-P rk Wald F", `rkf')
        local first_iv = 0
    }
    else {
        outreg2 using "`iv_file'", tex(frag) append ///
            addstat("Pre-COVID Y-Mean", `precovid_mean', ///
                    "K-P rk Wald F", `rkf')
    }
    
	if !`fs_done' {

		* grab stacked F-stats before restoring
		matrix FS = e(first)
		local partialF_3 = FS[4,1]
		local partialF_5 = FS[4,2]

		* ---- var3 first stage ----
		estimates restore _ivreg2_var3
		outreg2 using "`fs_file'", tex replace ///
			addstat("Partial F", `partialF_3', "KP rk Wald F", `rkf')

		* ---- var5 first stage ----
		estimates restore _ivreg2_var5
		outreg2 using "`fs_file'", tex append  
			addstat("Partial F", `partialF_5', "KP rk Wald F", `rkf')

		local fs_done 1
	}
	
}
