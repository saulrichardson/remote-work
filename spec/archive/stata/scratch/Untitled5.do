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
* firm_scaling_role_growth_groups.do
* ------------------------------------------------------------
* Firm-scaling regressions (OLS + IV) on grouped occupations.
* Groups: Ops/Admin, Marketing/Sales, Finance, Technical.
*============================================================*

clear all
set more off

// -----------------------------------------------------------------------------
// 0. Resolve project paths
// -----------------------------------------------------------------------------
// Prefer globals.do if the caller has set it up, but fall back to absolute paths
capture confirm file "../globals.do"
if !_rc {
    do "../globals.do"
}
else {
    global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
    global results         "/Users/saul/Dropbox/Remote Work Startups/main/results"
}

// Ensure required globals exist
if "${processed_data}" == "" {
    display as error "processed_data global not set."
    exit 198
}
if "${results}" == "" {
    display as error "results global not set."
    exit 198
}

// -----------------------------------------------------------------------------
// 1. Logging + output directories
// -----------------------------------------------------------------------------
local specname "firm_scaling_role_growth_groups"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text

capture mkdir "log"

local result_dir "${results}/raw/`specname'"
capture mkdir "${results}/raw"
capture mkdir "`result_dir'"

display as text "============================================================"
display as text "Running grouped occupation growth regressions"
display as text "Results directory: `result_dir'"
display as text "============================================================"

// -----------------------------------------------------------------------------
// 2. Load firm panel with baseline regressors
// -----------------------------------------------------------------------------
use "${processed_data}/firm_panel.dta", clear

keep firm_id companyname yh covid var3 var4 var5 var6 var7
order firm_id companyname yh covid var3 var4 var5 var6 var7

tempfile firm_base
save `firm_base'

// -----------------------------------------------------------------------------
// 3. Build grouped occupation growth dataset
// -----------------------------------------------------------------------------
import delimited "${processed_data}/role_k7_scaling_growth.csv", clear

replace role_k7 = trim(role_k7)
replace role_k7 = subinstr(role_k7, " ", "", .)
replace role_k7 = subinstr(role_k7, `"""', "", .)

// Map individual roles into grouped categories
keep if inlist(role_k7, "Admin", "Engineer", "Finance", "Marketing", "Operations", "Sales", "Scientist")

gen str15 role_group = ""
replace role_group = "OpsAdmin"        if inlist(role_k7, "Admin", "Operations")
replace role_group = "MarketingSales" if inlist(role_k7, "Marketing", "Sales")
replace role_group = "Finance"        if role_k7 == "Finance"
replace role_group = "Technical"      if inlist(role_k7, "Engineer", "Scientist")
keep if role_group != ""

replace prev_count      = 0 if missing(prev_count)
replace employee_count  = 0 if missing(employee_count)

// Align time index with firm panel (Stata half-year index)
gen yh = yh(year, half)

// Collapse to grouped role counts and compute growth rates
collapse (sum) employee_count prev_count, by(companyname yh role_group)

gen double growth_ = .
replace growth_ = (employee_count - prev_count) / prev_count if prev_count > 0

keep companyname yh role_group growth_
reshape wide growth_, i(companyname yh) j(role_group) string

// Merge onto firm panel
merge 1:1 companyname yh using `firm_base'
keep if _merge == 3
drop _merge

display as text "Merged grouped role growth data with firm panel: " _N " observations"

// -----------------------------------------------------------------------------
// 4. Winsorize role growth rates to match firm-scaling convention
// -----------------------------------------------------------------------------
capture which winsor2
if _rc {
    quietly ssc install winsor2, replace
}

local roles "OpsAdmin MarketingSales Finance Technical"
local label_OpsAdmin "Ops/Admin"
local label_MarketingSales "Marketing/Sales"
local label_Finance "Finance"
local label_Technical "Technical"
local growth_vars ""

foreach r of local roles {
    capture confirm variable growth_`r'
    if !_rc {
        local growth_vars "`growth_vars' growth_`r'"
    }
    else {
        display as error "Warning: growth_`r' not found after reshape"
    }
}

if "`growth_vars'" != "" {
    winsor2 `growth_vars', cuts(1 99) suffix(_we)
}
else {
    display as error "No growth variables found — exiting"
    exit 200
}

// -----------------------------------------------------------------------------
// 5. Set up storage for regression output
// -----------------------------------------------------------------------------
tempfile out_main out_fs

capture postclose handle
postfile handle ///
    str8   model_type ///
    str40  outcome    ///
    str12  param      ///
    double coef se pval pre_mean rkf nobs ///
    using `out_main', replace

capture postclose handle_fs
postfile handle_fs ///
    str8   endovar ///
    str12  param   ///
    double coef se pval partialF rkf nobs ///
    using `out_fs', replace

local fs_done 0

// -----------------------------------------------------------------------------
// 6. Loop over occupations and run OLS + IV
// -----------------------------------------------------------------------------
foreach r of local roles {
    capture confirm variable growth_`r'_we
    if _rc {
        display as error "Skipping `r': winsorized growth variable missing"
        continue
    }

    local yvar  = "growth_`r'_we"
    local yname = "growth_`r'"
    local pretty = "`label_`r''"

    display as text _n "→ Outcome: `pretty'"

    count if !missing(`yvar')
    local sampleN = r(N)
    display as text "   Non-missing observations: `sampleN'"
    if (`sampleN' < 200) {
        display as error "   Skipping `pretty' (insufficient support)"
        continue
    }

    summarize `yvar' if covid == 0, meanonly
    local pre_mean = r(mean)

    // ----------------------- OLS -------------------------------
    capture noisily reghdfe `yvar' var3 var5 var4, absorb(firm_id yh) vce(cluster firm_id)
    if (_rc) {
        display as error "   OLS failed for `pretty' (return code `_rc'). Skipping."
        continue
    }
    local N = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`yname'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    // ----------------------- IV -------------------------------
    capture noisily ivreghdfe `yvar' (var3 var5 = var6 var7) var4, ///
        absorb(firm_id yh) vce(cluster firm_id) savefirst
    if (_rc) {
        display as error "   IV failed for `pretty' (return code `_rc'). Skipping IV output."
        continue
    }

    local rkf = e(rkf)
    local N   = e(N)

    foreach p in var3 var5 var4 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`yname'") ("`p'") ///
            (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }

    // First-stage export (once, since instruments identical across outcomes)
    if !`fs_done' {
        matrix FS = e(first)
        local F3 = FS[4,1]
        local F5 = FS[4,2]

        estimates restore _ivreg2_var3
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var3") ("`p'") ///
                (`b') (`se') (`pval') (`F3') (`rkf') (`N_fs')
        }

        estimates restore _ivreg2_var5
        local N_fs = e(N)
        foreach p in var6 var7 var4 {
            local b    = _b[`p']
            local se   = _se[`p']
            local t    = `b'/`se'
            local pval = 2*ttail(e(df_r), abs(`t'))
            post handle_fs ("var5") ("`p'") ///
                (`b') (`se') (`pval') (`F5') (`rkf') (`N_fs')
        }

        local fs_done 1
    }
}

drop var3 var4 var5 var6 var7


bys companyname: egen post_tech = mean(growth_Technical_we) if covid == 1
// replace post_tech = 0 if missing(post_tech)


bys companyname: egen post_finance = mean(growth_Finance_we) if covid == 1
replace post_finance = 0 if missing(post_finance)


bys companyname: egen post_ops = mean(growth_OpsAdmin_we) if covid == 1
replace post_ops = 0 if missing(post_ops)


bys companyname: egen post_sales = mean(growth_MarketingSales_we) if covid == 1
replace post_sales = 0 if missing(post_sales)






// bys companyname: egen post_tech_2 = max(post_tech)

keep firm_id yh post*


merge 1:m firm_id yh using "/Users/saul/Dropbox/Remote Work Startups/main/data/processed/user_panel_precovid.dta"




reghdfe total_contributions_q100 var3 var5 var4, absorb(firm_id#user_id yh) vce(cluster firm_id)

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
        absorb(firm_id#user_id yh) vce(cluster firm_id) 
		


gen var17 = post_finance * startup * covid
gen var18 =  post_finance * covid

xtile tile_post_17 = var17, nq(2)
xtile tile_post_18 = var18, nq(2)

gen var19 = post_ops * startup * covid
gen var20 =  post_ops * covid

xtile tile_post_19 = var19, nq(2)
xtile tile_post_20 = var20, nq(2)

gen var21 = post_tech * startup * covid
gen var22 =  post_tech * covid

xtile tile_post_21 = var21, nq(2)
xtile tile_post_22 = var22, nq(2)

gen var23 = post_sales * startup * covid
gen var24 =  post_sales * covid

xtile tile_post_23 = var23, nq(2)
xtile tile_post_24 = var24, nq(2)



reghdfe total_contributions_q100 var3 var5 var4 var17 var18 tile_post_21 tile_post_22, absorb(firm_id#user_id yh) vce(cluster firm_id)

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 tile_post_21 tile_post_22, ///
        absorb(firm_id#user_id yh) vce(cluster firm_id) 


// -----------------------------------------------------------------------------
// 7. Export results
// -----------------------------------------------------------------------------
postclose handle
use `out_main', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

postclose handle_fs
use `out_fs', clear
export delimited using "`result_dir'/first_stage.csv", replace delimiter(",") quote

// Create a summary file for covid × remote (var3) across roles
use `out_main', clear
keep if param == "var3"
gen outcome_role = substr(outcome, 8, .)
replace outcome_role = "Ops/Admin"          if outcome_role == "OpsAdmin"
replace outcome_role = "Marketing/Sales"    if outcome_role == "MarketingSales"
replace outcome_role = "Finance"            if outcome_role == "Finance"
replace outcome_role = "Technical"         if outcome_role == "Technical"
order model_type outcome_role coef se pval pre_mean rkf nobs
export delimited using "`result_dir'/role_growth_groups_var3_summary.csv", replace delimiter(",") quote

// -----------------------------------------------------------------------------
// 8. Close log
// -----------------------------------------------------------------------------
display as result _n "Grouped role growth regressions written to:"
display as result "  - `result_dir'/consolidated_results.csv"
display as result "  - `result_dir'/first_stage.csv"
display as result "  - `result_dir'/role_growth_groups_var3_summary.csv"

capture log close
exit
