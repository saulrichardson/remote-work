*============================================================*
* Asset 10: user_productivity_precovid_nonsoftware.tex
* Self-contained firm×user FE nonsoftware robustness filters.
*============================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

local asset_stem "10_user_productivity_`panel_variant'_nonsoftware"

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

local result_root "$results/`asset_stem'"
capture mkdir "`result_root'"

local base_panel "$processed_data/user_panel_`panel_variant'.dta"
capture confirm file "`base_panel'"
if _rc {
    di as error "Panel file not found: `base_panel'"
    exit 601
}

local soc_core_2010 "15-1111 15-1121 15-1122 15-1131 15-1132 15-1133 15-1134 15-1141 15-1142 15-1143 15-1151 15-1152 15-1199 15-1256"

use "`base_panel'", clear
tempvar soc_core_new naics6_num naics2 naics4
gen byte `soc_core_new' = 0
foreach code of local soc_core_2010 {
    replace `soc_core_new' = 1 if trim(soc_new) == "`code'"
}

capture confirm numeric variable naics6
if !_rc {
    gen double `naics6_num' = naics6
}
else {
    destring naics6, gen(`naics6_num') force
}
replace `naics6_num' = . if `naics6_num' <= 0
gen int `naics2' = floor(`naics6_num'/10000) if `naics6_num' < .
gen int `naics4' = floor(`naics6_num'/100) if `naics6_num' < .

tempfile source_panel
save `source_panel', replace

program define run_filtered_spec
    args result_dir

    capture mkdir "`result_dir'"

    capture postclose handle
    tempfile out
    postfile handle ///
        str8   model_type ///
        str16  fe_tag ///
        str40  outcome ///
        str40  param ///
        double coef se pval pre_mean ///
        double rkf nobs ///
        using `out', replace

    local outcome total_contributions_q100
    local fe_tag firmXuser_yh
    local feopt "absorb(firm_id#user_id yh)"

    summarize `outcome' if covid == 0, meanonly
    local pre_mean = r(mean)

    reghdfe `outcome' var3 var5 var4, `feopt' vce(cluster user_id)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`fe_tag'") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (.) (`N')
    }

    ivreghdfe `outcome' (var3 var5 = var6 var7) var4, ///
        `feopt' vce(cluster user_id)
    local rkf = e(rkf)
    local N = e(N)
    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`fe_tag'") ("`outcome'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') ///
            (`rkf') (`N')
    }

    postclose handle
    use `out', clear
    export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote
end

foreach tag in naics_software soc_strict_new exclude_ca_ny {
    use `source_panel', clear

    if "`tag'" == "naics_software" {
        drop if inlist(`naics4', 5415) | inlist(`naics6_num', 541511, 541512, 541513, 541514, 541519)
    }
    else if "`tag'" == "soc_strict_new" {
        drop if `soc_core_new' == 1
    }
    else if "`tag'" == "exclude_ca_ny" {
        drop if missing(state) | trim(state)=="" | lower(trim(state))=="empty"
        drop if inlist(upper(trim(state)), "CA", "NY")
    }

    quietly count
    di as text "Filter `tag' observations: " %12.0fc r(N)
    run_filtered_spec "`result_root'/`tag'"
}

log close
