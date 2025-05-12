* ---------- 1. project-level globals --------------------------------
do "../src/globals.do"     

local specname   "firm_scaling_alternative_fe"
local result_path "$results/`specname'"
capture mkdir "`result_path'"

* ---------- 2. FE keywords & outcomes -------------------------------
local fe_keywords firmyh time firm none 
local outcomes growth_rate_we join_rate_we leave_rate_we

* ---------- 3. OUTER LOOP over FE keywords --------------------------
foreach fe of local fe_keywords {

    * --- map keyword → absorb-list & short tag ----------------------
    if      "`fe'"=="firmyh" {
        local absorb "firm_id yh"
        local tag    "ufy"
    }
    else if "`fe'"=="time" {
        local absorb "yh"
        local tag    "time"
    }
    else if "`fe'"=="firm" {
        local absorb "firm_id"
        local tag    "firm"
	}
    else {                        
        local absorb ""
        local tag    "none"
    }

    * --- build absorb() option only when it's non-empty -------------
    if "`absorb'"=="" {
        local feopt ""                              // no absorb() at all
    }
    else {
        local feopt "absorb(`absorb')"              // full absorb() clause
    }

    * --- results sub-folder & file handles --------------------------
    local fe_path "`result_path'/`tag'"
    capture mkdir "`fe_path'"

    local ols_file "`fe_path'/ols_results.tex"
    local iv_file  "`fe_path'/iv_results.tex"
    local fs_file  "`fe_path'/first_stage.tex"

    local first_ols 1
    local first_iv  1
    local fs_done   0

    di as res ">> FE spec: `fe'   (results → `fe_path')"

    * ---------- reload data so every spec uses identical sample -----
    use "$processed_data/firm_panel.dta", clear

    * ---------- INNER LOOP over outcomes ---------------------------
    foreach outcome of local outcomes {

        di as txt "   Outcome: `outcome'"

        * ----- OLS --------------------------------------------------
        reghdfe `outcome' var3 var5 var4, ///
            `feopt' vce(cluster firm_id)

        quietly summarize `outcome' if covid == 0
        local precovid_mean = r(mean)

        outreg2 using "`ols_file'", tex ///
            `=cond(`first_ols', "replace", "append")' ///
            ctitle("OLS `outcome' (FE: `tag')") ///
            addstat("Pre-COVID Y-Mean", `precovid_mean')
        local first_ols 0


        * ----- IV ---------------------------------------------------
        ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
            `feopt' vce(cluster firm_id) savefirst

        quietly summarize `outcome' if covid == 0
        local precovid_mean = r(mean)
        local rkf = e(rkf)

        outreg2 using "`iv_file'", tex ///
            `=cond(`first_iv', "replace", "append")' ///
            ctitle("IV `outcome' (FE: `tag')") ///
            addstat("Pre-COVID Y-Mean", `precovid_mean', ///
                    "KP rk Wald F", `rkf')
        local first_iv 0



*---------------------------------------------------------------------------
*  FIRST-STAGE TABLE  (run once per FE recipe, no loops, no tricks)
*---------------------------------------------------------------------------
	if !`fs_done' {

		* grab stacked F-stats before restoring
		matrix FS = e(first)
		local partialF_3 = FS[4,1]
		local partialF_5 = FS[4,2]

		* ---- var3 first stage ----
		estimates restore _ivreg2_var3

		* check if partialF_3 is missing
		if missing(`partialF_3') {
			outreg2 using "`fs_file'", tex(frag) replace ///
				addstat("KP rk Wald F", `rkf')
		}
		else {
			outreg2 using "`fs_file'", tex(frag) replace ///
				addstat("Partial F", `partialF_3', "KP rk Wald F", `rkf')
		}


		* ---- var5 first stage ----
		estimates restore _ivreg2_var5

		* check if partialF_5 is missing
		if missing(`partialF_5') {
			outreg2 using "`fs_file'", tex(frag) append ///
				addstat("KP rk Wald F", `rkf')
		}
		else {
			outreg2 using "`fs_file'", tex(frag) append ///
				addstat("Partial F", `partialF_5', "KP rk Wald F", `rkf')
		}

		local fs_done 1
	}


    }
}

di as res "✓ All specifications finished — see `result_path'"
