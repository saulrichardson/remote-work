// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"


*============================================================*
* spec/user_productivity_mechanisms.do
*  Baseline user productivity diff-in-diff with rent, HHI,
*  and seniority interaction variants (OLS + IV).
*  Assumes execution from the repository root.
*============================================================*


do "../globals.do"

local specname   "user_quad"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

local result_dir "$results/`specname'"
cap mkdir "`result_dir'"



args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"




use "$processed_data/user_panel_`panel_variant'.dta", clear

// Seniority flag (L4+) used for interaction specification
gen byte seniority_4 = !inrange(seniority_levels, 1, 3)
replace seniority_4 = . if missing(seniority_levels)


capture postclose handle
tempfile out
postfile handle ///
    str8  model_type ///
    str12 spec       ///
    str24 param      ///
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

local outcome_vars "total_contributions_q100"
local specs "baseline rent hhi seniority"

foreach spec of local specs {
    local exog    "var4"
    local endo    "var3 var5"
    local instr   "var6 var7"
    local params  "var3 var5 var4"
    local filter  ""
    local suffix  ""

    if "`spec'" == "rent" {
        local mechanism "rent"
        local suffix    "_rent"
        local filter    "!missing(`mechanism')"
    }
    else if "`spec'" == "hhi" {
        local mechanism "hhi_1000"
        local suffix    "_hhi"
        local filter    "!missing(`mechanism')"
    }
    else if "`spec'" == "seniority" {
        local mechanism "seniority_4"
        local suffix    "_sen"
        local filter    "!missing(`mechanism')"
    }

    if "`spec'" != "baseline" {
        capture drop var3`suffix' var5`suffix' var4`suffix' var6`suffix' var7`suffix'
        gen double var3`suffix' = var3*`mechanism'
        gen double var5`suffix' = var5*`mechanism'
        gen double var4`suffix' = var4*`mechanism'
        gen double var6`suffix' = var6*`mechanism'
        gen double var7`suffix' = var7*`mechanism'

        local exog   "`exog' var4`suffix'"
        local endo   "`endo' var3`suffix' var5`suffix'"
        local instr  "`instr' var6`suffix' var7`suffix'"
        local params "`params' var3`suffix' var5`suffix' var4`suffix'"
    }

    foreach y of local outcome_vars {
        if "`filter'" == "" {
             summarize `y' if covid == 0, meanonly
        }
        else {
             summarize `y' if covid == 0 & `filter', meanonly
        }
        if r(N) == 0 continue
        local pre_mean = r(mean)

        local ifcmd ""
        if "`filter'" != "" local ifcmd "if `filter'"

         reghdfe `y' `endo' `exog' `ifcmd', ///
            absorb(firm_id#user_id yh) vce(cluster user_id)
        local N = e(N)
        foreach p of local params {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("OLS") ("`spec'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') (.) (`N')
        }

         ivreghdfe `y' (`endo' = `instr') `exog' `ifcmd', ///
            absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
        local rkf = e(rkf)
        local N   = e(N)
        foreach p of local params {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle ("IV") ("`spec'") ("`p'") ///
                (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
        }
    }

    if "`spec'" != "baseline" {
        drop var3`suffix' var5`suffix' var4`suffix' var6`suffix' var7`suffix'
    }
}

postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", ///
    replace delimiter(",") quote

log close
