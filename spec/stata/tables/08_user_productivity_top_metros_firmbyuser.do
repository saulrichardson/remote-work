*============================================================*
* Asset 08: user_productivity_top_metros_firmbyuser.tex
* Self-contained firm×user FE top-metro scenarios.
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local asset_stem "08_user_productivity_top_metros_firmbyuser"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`asset_stem'.log", replace text

local base_panel "$processed_data/user_panel_`panel_variant'.dta"
capture confirm file "`base_panel'"
if _rc {
    di as error "Panel file not found: `base_panel'"
    exit 601
}

local mapping_file "$PROJECT_ROOT/data/clean/csa_msa_top14_mapping.csv"
capture confirm file "`mapping_file'"
if _rc {
    di as error "Mapping file missing: `mapping_file'"
    exit 601
}

local result_root "$results/`asset_stem'"
capture mkdir "`result_root'"

capture which reghdfe
if _rc exit 199
capture which ivreghdfe
if _rc exit 199

program define run_firmbyuser_spec
    args result_dir

    capture mkdir "`result_dir'"

    capture postclose handle
    tempfile out
    postfile handle ///
        str8   model_type ///
        str40  outcome ///
        str40  param ///
        double coef se pval pre_mean ///
        double rkf nobs ///
        using `out', replace

    local outcome total_contributions_q100
    summarize `outcome' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `outcome' var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id#user_id yh) cluster(user_id)
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    postclose handle
    use `out', clear
    export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
end

tempfile csa_map
import delimited using "`mapping_file'", varnames(1) clear
quietly summarize csa_rank
local max_rank = r(max)
save `csa_map', replace

local scenarios ///
    "`panel_variant'_keeptop5 `panel_variant'_keeptop10 `panel_variant'_droptop5 `panel_variant'_droptop10"

foreach scenario of local scenarios {
    local cutoff = .
    local mode ""
    if "`scenario'" == "`panel_variant'_keeptop5" {
        local cutoff = 5
        local mode "keep"
    }
    else if "`scenario'" == "`panel_variant'_keeptop10" {
        local cutoff = 10
        local mode "keep"
    }
    else if "`scenario'" == "`panel_variant'_droptop5" {
        local cutoff = 5
        local mode "drop"
    }
    else if "`scenario'" == "`panel_variant'_droptop10" {
        local cutoff = 10
        local mode "drop"
    }
    else {
        continue
    }

    use `csa_map', clear
    local effective_rank = `cutoff'
    if `effective_rank' > `max_rank' local effective_rank = `max_rank'
    keep if csa_rank <= `effective_rank'
    gen byte scenario_flag = 1
    keep cbsacode scenario_flag
    rename cbsacode company_cbsacode
    duplicates drop
    tempfile scenario_codes
    save `scenario_codes', replace

    use "`base_panel'", clear
    capture confirm numeric variable company_cbsacode
    if _rc {
        destring company_cbsacode, replace force
    }

    if "`mode'" == "keep" {
        merge m:1 company_cbsacode using `scenario_codes', keep(match) nogen
    }
    else if "`mode'" == "drop" {
        merge m:1 company_cbsacode using `scenario_codes', keep(master match) nogen
        drop if scenario_flag == 1
        drop scenario_flag
    }

    quietly count
    di as text "Scenario `scenario' observations: " %12.0fc r(N)
    run_firmbyuser_spec "`result_root'/`scenario'"
}

log close
