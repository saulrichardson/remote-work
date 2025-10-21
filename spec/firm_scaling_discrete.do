*============================================================*
*  do/firm_scaling_regressions.do
*  — Automated export of OLS, IV, and first‐stage partial F's
*============================================================*

args  treat
if "`treat'"         == "" local treat         "hybrid"

// 0) Setup environment
do "../src/globals.do"

// 1) Load master panel
use "$processed_data/firm_panel.dta", clear

// 2) Prepare output dir & tempfile
local specname   firm_scaling_`treat'
capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

local result_dir "$results/`specname'"
capture mkdir "`result_dir'"



capture postclose handle
tempfile out
*--- postfile header (main results) -------------------------------------------
postfile handle ///
    str8   model_type ///
    str40  outcome     ///
    str40  param       ///
    double coef se pval pre_mean ///
    double rkf nobs     ///
    using `out', replace


*------------------------------------------------------------------
*  First-stage results → first_stage_fstats.csv
*------------------------------------------------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str8   endovar            ///  var3 / var5
    str40  param              ///  var6 / var7 / var4
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace


if "`treat'" == "fullremote" {
    local v3 = "var3_fullrem"
    local v5 = "var5_fullrem"
    // Ensure required interactions exist even if not present in panel
    capture confirm variable var3_fullrem
    if _rc {
        gen byte fullrem = (remote==1)
        gen var3_fullrem = fullrem * covid
        gen var5_fullrem = fullrem * covid * startup
    }
}
else if "`treat'" == "hybrid" {
    local v3 = "var3_hybrid"
    local v5 = "var5_hybrid"
    capture confirm variable var3_hybrid
    if _rc {
        gen byte hybrid = (remote>0 & remote<1)
        gen var3_hybrid = hybrid * covid
        gen var5_hybrid = hybrid * covid * startup
    }
}
else if "`treat'" == "inperson" {
    local v3 = "var3_inperson"
    local v5 = "var5_inperson"
    capture confirm variable var3_inperson
    if _rc {
        gen byte inperson = (remote==0)
        gen var3_inperson = inperson * covid
        gen var5_inperson = inperson * covid * startup
    }
}
else if "`treat'" == "anyremote" {
    local v3 = "var3_anyremote"
    local v5 = "var5_anyremote"
    capture confirm variable var3_anyremote
    if _rc {
        gen byte anyremote = (remote>0)
        gen var3_anyremote = anyremote * covid
        gen var5_anyremote = anyremote * covid * startup
    }
}
else if "`treat'" == "nonremote" {
    local v3 = "var3_nonrem"
    local v5 = "var5_nonrem"
    capture confirm variable var3_nonrem
    if _rc {
        gen byte nonrem = (remote==0)
        gen var3_nonrem = nonrem * covid
        gen var5_nonrem = nonrem * covid * startup
    }
}
else {
    di as error "Unknown treat=`treat'—must be fullremote, hybrid, inperson, anyremote, or nonremote"
    exit 1
}

// 3) Loop over outcomes
local outcome_vars growth_rate_we join_rate_we leave_rate_we

local fs_done = 0

foreach y of local outcome_vars {
    di as text "→ Processing `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // --- OLS ---
     reghdfe `y' `v3' `v5' var4, absorb(firm_id yh) vce(cluster firm_id)
	
	local N = e(N) 

    foreach p in `v3' `v5' var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("OLS") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')                 // dot for rkf, then nobs
    }

    // --- IV (2nd stage) ---
     ivreghdfe ///
        `y' (`v3' `v5' = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst

    local rkf   = e(rkf)
	local N = e(N) 

    foreach p in `v3' `v5' var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
		*--- inside the IV loop -------------------------------------------------------
                post handle ("IV") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')            // rkf, then nobs
    }

    // --- FIRST STAGE: only once on first loop pass ---
// 	if !`fs_done' {
		
// 		matrix FS = e(first)
//         local F3 = FS[4,1]
//         local F5 = FS[4,2]
//
// 		/* -------- var3 first stage -------------------------------- */
// 		estimates restore _ivreg2_var3
// 		local N_fs = e(N)
// 		foreach p in var6 var7 var4 {
// 			local b    = _b[`p']
// 			local se   = _se[`p']
// 			local t    = `b'/`se'
// 			local pval = 2*ttail(e(df_r), abs(`t'))
//
// 			post handle_fs ("v3") ("`p'") ///
// 							(`b') (`se') (`pval') ///
// 							(`F3') (`rkf') (`N_fs')
// 		}
//
// 		/* -------- var5 first stage -------------------------------- */
// 		estimates restore _ivreg2_var5
// 		local N_fs = e(N)
// 		foreach p in var6 var7 var4 {
// 			local b    = _b[`p']
// 			local se   = _se[`p']
// 			local t    = `b'/`se'
// 			local pval = 2*ttail(e(df_r), abs(`t'))
//
// 			post handle_fs ("v5") ("`p'") ///
// 							(`b') (`se') (`pval') ///
// 							(`F5') (`rkf') (`N_fs')
// 		}

// 		local fs_done 1
// 	}

}


// 4) Close & export to CSV
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

* --- write first-stage CSV -----------------------------------------
postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", ///
        replace delimiter(",") quote

di as result "→ second-stage CSV : `result_dir'/consolidated_results.csv"
di as result "→ first-stage  CSV : `result_dir'/first_stage.csv"
