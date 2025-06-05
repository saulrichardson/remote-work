*============================================================*
*  do/firm_scaling_alternative_fe_regressions.do
*  — Automated export of OLS, IV, and first‐stage F's
*    across four explicit FE specifications
*============================================================*
capture log close
local specname  "user_productivity_alternative_fe"
log using "log/`specname'.log", replace text

// 0) Setup environment
do "../src/globals.do"

// 1) Common settings
local result_dir "$results/`specname'"
capture mkdir "`result_dir'"

local outcomes total_contributions_q100 
// restricted_contributions_q100

*--- main results -------------------------------------------------------------
tempfile out  
capture postclose handle
postfile handle ///
    str20   model_type          ///
    str20   fe_tag              ///
    str40  outcome             ///
    str40  param               ///
    double coef se pval pre_mean ///
    double rkf nobs            ///
    using `out', replace


*--- first-stage results (coefficients + diagnostics) -------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str20   fe_tag              ///  "fyh", "time", "firm", "none"
    str40  outcome             ///
    str20   endovar             ///  "var3" / "var5"
    str40  param               ///  var6 / var7 / var4
    double coef se pval        ///
    double partialF rkf nobs   ///
    using `out_fs', replace

	
//-------------------------------------------------------------
// Firm + user + year FE ("fyh")
//-------------------------------------------------------------
local feopt "absorb(firm_id user_id yh)"
local tag   "fyhu"


foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}



//-------------------------------------------------------------
// firm x user + yh
//-------------------------------------------------------------
local feopt "absorb(firm_id#user_id yh)"
local tag   "firmbyuseryh"


foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"
    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}




//-------------------------------------------------------------
//  Firm + year FE ("fyh")
//-------------------------------------------------------------
local feopt "absorb(firm_id yh)"
local tag   "fyh"

foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"
    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}



local feopt "absorb(user_id yh)"
local tag   "useryh"

foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"
    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}


//-------------------------------------------------------------
// Time FE ("time")
//-------------------------------------------------------------
local feopt "absorb(yh)"
local tag   "time"

foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear

        gen var8 = remote * startup
        gen var9 = teleworkable*startup

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)
	
    display as text ">> FE spec: time  (tag=`tag')"
    display as text "   – outcome: `y'"

    // OLS
    reghdfe `y' var3 var5 var4 remote startup var8 covid, ///
        `feopt' vce(cluster user_id)
	local N   = e(N)
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 var8 remote = var6 var7 var9 teleworkable) var4 startup covid, ///
        `feopt' vce(cluster user_id) savefirst
		
    local rkf = e(rkf)
	local N   = e(N)
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }

	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}

//-------------------------------------------------------------
// Firm FE ("firm")
//-------------------------------------------------------------
local feopt "absorb(firm_id)"
local tag   "firm"

foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear

    display as text ">> FE spec: firm  (tag=`tag')"
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4 covid, ///
        `feopt' vce(cluster user_id)
	
	local N   = e(N)
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4 covid, ///
        `feopt' vce(cluster user_id) savefirst
		
    local rkf = e(rkf)
	local N   = e(N)
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }

	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}

//-------------------------------------------------------------
// No FE ("none")
//-------------------------------------------------------------
local feopt ""
local tag   "none"

foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
	
	gen var8 = remote * startup
    gen var9 = teleworkable*startup

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    display as text ">> FE spec: none  (tag=`tag')"
    display as text "   – outcome: `y'"

    // OLS
    reghdfe `y' var3 var5 var4 remote startup var8 covid, ///
        absorb() vce(cluster user_id)
		
	local N   = e(N)
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
    ivreghdfe ///
        `y' (var3 var5 var8 remote = var6 var7 var9 teleworkable) var4 startup covid, ///
        absorb() vce(cluster user_id) savefirst
    local rkf = e(rkf)
	local N   = e(N)
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }

	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}



local feopt "absorb(firm_id user_id industry_id#yh)"
local tag   "industrytime"


foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}


local feopt "absorb(firm_id user_id msa_id#yh)"
local tag   "msatime"


foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}




local feopt "absorb(firm_id user_id msa_id#industry_id#yh)"
local tag   "msaindustrytime"


foreach y of local outcomes {
    use "$processed_data/user_panel_${user_panel_variant}.dta", clear
    display as text ">> FE spec: (tag=`tag')"
    display as text "   – outcome: `y'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

    // OLS
     reghdfe `y' var3 var5 var4, ///
        `feopt' vce(cluster user_id)
		
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))

                post handle ("OLS") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (.) (`N')
    }

    // IV (2nd stage)
     ivreghdfe ///
        `y' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id) savefirst
    
	local rkf = e(rkf)
	local N = e(N)  
	
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
                post handle ("IV") ("`tag'") ("`y'") ("`p'") ///
                                        (`b') (`se') (`pval') (`pre_mean') ///
                                        (`rkf') (`N')
    }
	
	*--- pull partial F's from the stacked matrix
	matrix FS = e(first)
	local F3 = FS[4,1]
	local F5 = FS[4,2]

	*========= var3 first stage ===================================================
	estimates restore _ivreg2_var3
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var3") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F3') (`rkf') (`N_fs')
	}

	*========= var5 first stage ===================================================
	estimates restore _ivreg2_var5
	local N_fs = e(N)

	foreach p in var6 var7 var4 {
		local b    = _b[`p']
		local se   = _se[`p']
		local t    = `b'/`se'
		local pval = 2*ttail(e(df_r), abs(`t'))

		post handle_fs ("`tag'") ("`y'") ("var5") ("`p'") ///
						(`b') (`se') (`pval') ///
						(`F5') (`rkf') (`N_fs')
	}

}




//-------------------------------------------------------------
// Close & export CSV
//-------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote
	
*------------------------------------------------------------
*  Write first-stage CSV to disk
*------------------------------------------------------------
postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage_fstats.csv", ///
        replace delimiter(",") quote
		

display as result "→ main CSV       : `result_dir'/consolidated_results.csv"
display as result "→ first-stage CSV: `result_dir'/first_stage_fstats.csv"

log close
