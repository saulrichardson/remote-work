*============================================================*
* user_productivity_robustness.do
* Copies the baseline user-level regressions and adds sample filters
* to run robustness checks.  Supported robustness tags:
*   baseline             – no additional filter (default)
*   no_tech_industry     – drop firm observations in Technology industry
*   no_tech_soc          – drop core tech SOC occupations (2010 block)
*   only_ca_ny           – keep jobs located in CA or NY
*   exclude_ca_ny        – drop jobs located in CA or NY
*============================================================*

* --------------------------------------------------------------------------
* 0) Parse optional variant argument *before* bootstrapping paths -----------
* --------------------------------------------------------------------------

args panel_variant sample_tag
if "`panel_variant'" == "" local panel_variant "precovid"
if "`sample_tag'"     == "" local sample_tag "baseline"

* Manual toggles (comment/uncomment as needed)
global MANUAL_DROP_TECH        0   // drop Technology firms no matter the tag
global MANUAL_DROP_SOC         0   // drop core tech SOC occupations
global MANUAL_KEEP_ONLY_CA_NY  0   // keep only CA/NY observations
global MANUAL_DROP_CA_NY       0   // drop CA/NY observations

local soc_core_2010 "15-1111 15-1121 15-1122 15-1131 15-1132 15-1133 15-1134 15-1141 15-1142 15-1143 15-1151 15-1152 15-1199 15-1256"

local manual_suffix ""
if "$MANUAL_DROP_TECH" == "1"        local manual_suffix "`manual_suffix'_mtech"
if "$MANUAL_DROP_SOC" == "1"         local manual_suffix "`manual_suffix'_msoc"
if "$MANUAL_KEEP_ONLY_CA_NY" == "1"  local manual_suffix "`manual_suffix'_monlycany"
if "$MANUAL_DROP_CA_NY" == "1"       local manual_suffix "`manual_suffix'_mdropcany"

local resolved_tag "`sample_tag'"
if "`manual_suffix'" != "" {
    local manual_suffix = substr("`manual_suffix'", 2, .)
    if "`resolved_tag'" == "baseline" {
        local resolved_tag "manual_`manual_suffix'"
    }
    else {
        local resolved_tag "`resolved_tag'_`manual_suffix'"
    }
}

local specname user_productivity_`panel_variant'_`resolved_tag'
capture log close
cap mkdir "log"
log using "log/`specname'.log", replace text

// 0) Hard-code required paths (avoid bootstrap search)
global PROJECT_ROOT  "/Users/saul/Dropbox/Remote Work Startups/main"
global processed_data "$PROJECT_ROOT/data/processed"
global results        "$PROJECT_ROOT/results/raw"
global RAW_RESULTS    "$PROJECT_ROOT/results/raw"
global PROCESSED_DATA "$PROJECT_ROOT/data/processed"

// 1) Load worker‐level panel
use "$processed_data/user_panel_`panel_variant'.dta", clear

// Apply requested robustness filter
local sample_desc "No additional filter"
if "`sample_tag'" == "baseline" ///
    & "$MANUAL_DROP_TECH" == "0" ///
    & "$MANUAL_DROP_SOC" == "0" ///
    & "$MANUAL_KEEP_ONLY_CA_NY" == "0" ///
    & "$MANUAL_DROP_CA_NY" == "0" ///
    ///
{
    // no-op
}
else if "`sample_tag'" == "no_tech_industry" | "$MANUAL_DROP_TECH" == "1" {
    drop if industry_id == 20
    local sample_desc "Dropped Technology industry (industry_id==20)"
}
else if "`sample_tag'" == "no_tech_soc" | "$MANUAL_DROP_SOC" == "1" {
    tempvar __drop_soc
    gen byte `__drop_soc' = 0 if trim(soc_new)!=""
    foreach code of local soc_core_2010 {
        replace `__drop_soc' = 1 if soc_new == "`code'"
    }
    drop if `__drop_soc' == 1
    drop `__drop_soc'
    local sample_desc "Dropped SOC 2010 core tech occupations"
}
else if inlist("`sample_tag'", "only_ca_ny", "exclude_ca_ny") ///
        | "$MANUAL_KEEP_ONLY_CA_NY" == "1" | "$MANUAL_DROP_CA_NY" == "1" {
    drop if missing(state) | trim(state)=="" | lower(trim(state))=="empty"
    if "`sample_tag'" == "only_ca_ny" | "$MANUAL_KEEP_ONLY_CA_NY" == "1" {
        keep if inlist(upper(trim(state)), "CA", "NY")
        local sample_desc "Kept CA/NY job locations only"
    }
    else {
        drop if inlist(upper(trim(state)), "CA", "NY")
        local sample_desc "Dropped CA/NY job locations"
    }
}
else {
    di as error "Unknown sample_tag ``sample_tag''. Valid tags: baseline no_tech_industry no_tech_soc only_ca_ny exclude_ca_ny"
    exit 198
}

count
di as text "Sample tag: `resolved_tag' (`sample_desc'). Remaining observations: " %12.0fc r(N)

capture drop _merge
tempfile sample_data
save `sample_data', replace

local result_dir  "$results/`specname'"
capture mkdir "`result_dir'"

capture postclose handle
tempfile out
*--- postfile header (main results) -------------------------------------------
postfile handle ///
    str8   model_type ///
    str16  fe_tag     ///
    str40  outcome    ///
    str40  param      ///
    double coef se pval pre_mean ///
    double rkf nobs    ///
    using `out', replace


*------------------------------------------------------------------
*  First-stage results → first_stage_fstats.csv
*------------------------------------------------------------------
tempfile out_fs
capture postclose handle_fs
postfile handle_fs ///
    str16  fe_tag             ///
    str8   endovar            ///
    str40  param              ///
    double coef se pval       ///
    double partialF rkf nobs  ///
    using `out_fs', replace
		
// 3) Loop over outcomes & FE structures
local outcomes total_contributions_q100 
// restricted_contributions_q100 total_contributions_we restricted_contributions_we

local fe_tags "firm_user_yh firmXuser_yh"

foreach fe_tag of local fe_tags {
    if "`fe_tag'" == "firm_user_yh" {
        local feopt "absorb(firm_id user_id yh)"
    }
    else if "`fe_tag'" == "firmXuser_yh" {
        local feopt "absorb(firm_id#user_id yh)"
    }
    else {
        di as error "Unknown FE tag `fe_tag'"
        exit 198
    }
    local fs_done 0

    foreach y of local outcomes {
        use `sample_data', clear
        di as text "→ Processing outcome: `y' | FE: `fe_tag'"

    summarize `y' if covid == 0, meanonly
    local pre_mean = r(mean)

        // ----- OLS -----
        reghdfe `y' var3 var5 var4, `feopt' vce(cluster user_id)
		
    	local N = e(N) 
	
        foreach p in var3 var5 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("OLS") ("`fe_tag'") ("`y'") ("`p'") ///
                                            (`b') (`se') (`pval') (`pre_mean') ///
                                            (.) (`N')
        }

        // ----- IV (2nd‐stage) -----
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
            post handle ("IV") ("`fe_tag'") ("`y'") ("`p'") ///
                                            (`b') (`se') (`pval') (`pre_mean') ///
                                            (`rkf') (`N')
        }

    	if !`fs_done' {
		
    		matrix FS = e(first)
            local F3 = FS[4,1]
            local F5 = FS[4,2]

    		/* -------- var3 first stage -------------------------------- */
    		estimates restore _ivreg2_var3
    		local N_fs = e(N)
    		foreach p in var6 var7 var4 {
    			local b    = _b[`p']
    			local se   = _se[`p']
    			local t    = `b'/`se'
    			local pval = 2*ttail(e(df_r), abs(`t'))

    			post handle_fs ("`fe_tag'") ("var3") ("`p'") ///
    							(`b') (`se') (`pval') ///
    							(`F3') (`rkf') (`N_fs')
    		}

    		/* -------- var5 first stage -------------------------------- */
    		estimates restore _ivreg2_var5
    		local N_fs = e(N)
    		foreach p in var6 var7 var4 {
    			local b    = _b[`p']
    			local se   = _se[`p']
    			local t    = `b'/`se'
    			local pval = 2*ttail(e(df_r), abs(`t'))

    			post handle_fs ("`fe_tag'") ("var5") ("`p'") ///
    							(`b') (`se') (`pval') ///
    							(`F5') (`rkf') (`N_fs')
    		}

    		local fs_done 1
    	}
    }
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
capture log close
