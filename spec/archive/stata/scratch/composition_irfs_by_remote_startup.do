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
* composition_irfs_by_remote_startup.do
* 7-role IRFs on individual productivity via local projections,
* split by Remote (==1) × Startup (==1) groups.
* - Mirrors composition_irfs_by_startup.do
* - Adds remote flag and runs four group IRFs
* - Uses firm-cluster SEs and TS-based leads
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_by_remote_startup.log", replace text
set scheme s2color

//---------- Globals ----------//
// Try to use existing globals; else resolve relative; else absolute fallback
capture confirm file "$processed_data/user_panel_precovid.dta"
if _rc {
    capture confirm file "data/processed/user_panel_precovid.dta"
    if !_rc {
        global processed_data "data/processed"
        global base_results  "results"
    }
    else {
        capture confirm file "../data/processed/user_panel_precovid.dta"
        if !_rc {
            global processed_data "../data/processed"
            global base_results  "../results"
        }
        else {
            global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
            global base_results  "/Users/saul/Dropbox/Remote Work Startups/main/results"
        }
    }
}

global results_root "$base_results/composition_irfs_all7_by_remote_startup"
capture mkdir "$results_root"

display "============================================================="
display "7-ROLE IRFs: Remote×Startup splits"
display "Outcome: Individual Productivity Percentile"
display "============================================================="

//---------- STEP 1: Load user panel ----------//
display _n "STEP 1: Loading user panel"
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
assert !missing(user_id, firm_id, yh, total_contributions_q100)
display "User panel loaded: N=" %9.0fc _N

//---------- STEP 2: Load role growth wide ----------//
display _n "STEP 2: Loading role growths and reshaping wide"
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    gen yh = yh(year, half)
    gen companyname_c = lower(companyname)
    keep companyname_c yh role_k7 pct_growth_role role_share
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share*      share_*
    foreach v of varlist pct_growth_* share_* {
        replace `v' = 0 if missing(`v')
    }
    tempfile role_wide
    save `role_wide'
restore

//---------- STEP 3: Merge role growth into user panel ----------//
display _n "STEP 3: Merging role growths to user panel (companyname_c×yh)"
merge m:1 companyname_c yh using `role_wide'
display "Merge role growths:" 
tab _merge
keep if _merge == 3
drop _merge

//---------- STEP 4: Merge firm-time flags (remote, startup) ----------//
display _n "STEP 4: Merging firm-time flags (remote, startup)"
preserve
    use "$processed_data/firm_panel.dta", clear
    keep firm_id yh remote startup
    duplicates drop
    tempfile firm_flags
    save `firm_flags'
restore
merge m:1 firm_id yh using `firm_flags'
display "Merge remote/startup:" 
tab _merge
keep if _merge == 3
drop _merge

gen byte remote_bin = (remote == 1)
label var remote_bin "Fully remote (==1)"
label var startup    "Startup (==1)"

//---------- STEP 5: Panel and TS leads ----------//
display _n "STEP 5: Panel setup and TS leads"
xtset user_id yh
forvalues h = 0/4 {
    gen F`h'_prod = F`h'.total_contributions_q100
}

display _n "Sample sizes by horizon:"
forvalues h = 0/4 {
    count if !missing(F`h'_prod)
    display "  H`h': N=" %9.0fc r(N)
}

// Cache analytic
tempfile ANALYTIC
save `ANALYTIC'
global ANALYTIC "`ANALYTIC'"

//---------- STEP 6: Roles and estimator ----------//
local role_vars "pct_growth_Admin pct_growth_Engineer pct_growth_Finance pct_growth_Marketing pct_growth_Operations pct_growth_Sales pct_growth_Scientist"

program define run_group_irfs
    // args: varlist, if, label, outdir
    syntax varlist(min=1 numeric) [if], LABEL(string) OUTDIR(string)
    preserve
        use "$ANALYTIC", clear
        keep `if'
        count
        local N_all = r(N)
        display _n "Estimating 7-role IRFs for: `label' (N=" %9.0fc `N_all' ")"
        display as text "Vars: `varlist'"
        capture mkdir "`outdir'"

        tempname hdl
        capture postclose `hdl'
        postfile `hdl' str15 role horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`outdir'/all7_irf_estimates.dta", replace

        forvalues h = 0/4 {
            display "  -> Horizon `h'"
            quietly capture reghdfe F`h'_prod `varlist', absorb(user_id#firm_id yh) vce(cluster firm_id)
            display as text "     rc=`_rc'"
            if _rc == 0 {
                local N = e(N)
                local R2 = e(r2)
                foreach v of local varlist {
                    local rname = subinstr("`v'", "pct_growth_", "", .)
                    local b  = _b[`v']
                    local se = _se[`v']
                    local t  = `b'/`se'
                    local p  = 2*ttail(e(df_r), abs(`t'))
                    local lo = `b' - invttail(e(df_r), 0.025)*`se'
                    local hi = `b' + invttail(e(df_r), 0.025)*`se'
                    post `hdl' ("`rname'") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N') (`R2')
                }
            }
            else {
                foreach v of local varlist {
                    local rname = subinstr("`v'", "pct_growth_", "", .)
                    post `hdl' ("`rname'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
                }
            }
        }
        postclose `hdl'

        // Export CSV
        use "`outdir'/all7_irf_estimates.dta", clear
        export delimited using "`outdir'/all7_irf_results.csv", replace

        // Plots omitted in batch run; CSVs contain full estimates
    restore
end

//---------- STEP 7: Run 4 groups ----------//
display _n "STEP 7: Estimating by Remote×Startup groups"

local g1_if "remote_bin==0 & startup==0"
local g1_lab "Non-Remote, Non-Startup"
local g1_dir "$results_root/remote0_startup0"

local g2_if "remote_bin==1 & startup==0"
local g2_lab "Remote, Non-Startup"
local g2_dir "$results_root/remote1_startup0"

local g3_if "remote_bin==0 & startup==1"
local g3_lab "Non-Remote, Startup"
local g3_dir "$results_root/remote0_startup1"

local g4_if "remote_bin==1 & startup==1"
local g4_lab "Remote, Startup"
local g4_dir "$results_root/remote1_startup1"

run_group_irfs `role_vars' if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_group_irfs `role_vars' if `g2_if', label("`g2_lab'") outdir("`g2_dir'")
run_group_irfs `role_vars' if `g3_if', label("`g3_lab'") outdir("`g3_dir'")
run_group_irfs `role_vars' if `g4_if', label("`g4_lab'") outdir("`g4_dir'")

//---------- SUMMARY ----------//
display _n _n "============================================================="
display "7-role IRFs by Remote×Startup complete"
display "Outputs under: $results_root/"
display "============================================================="

log close
