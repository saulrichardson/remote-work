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
* user_irfs_engineer_by_remote.do
* Local projections of individual productivity on Engineer hiring
* growth (single regressor), split by:
*   - Fully remote firms (remote == 1)
*   - Hybrid/In-person firms (remote < 1)
* Reverts to the Engineer-only series (no Scientist aggregation).
* Mirrors FE/SE used in composition IRFs; startup split removed.
*============================================================*

clear all
set more off
capture log close
log using "user_irfs_engineer_by_remote.log", replace text
set scheme s2color

//---------- Globals ----------//
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

global results_root "$base_results/user_irfs_engineer_remote"
capture mkdir "$results_root"

display "============================================================="
display "User IRFs: Productivity on Engineer hiring growth"
display "Split: Fully Remote (remote==1) vs Hybrid/In-Person (remote<1)"
display "============================================================="

//---------- STEP 1: Load user panel ----------//
display _n "STEP 1: Loading user panel"
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
assert !missing(user_id, firm_id, yh, total_contributions_q100)
display "User panel loaded: N=" %9.0fc _N

//---------- STEP 2: Build Engineer growth from role data ----------//
display _n "STEP 2: Construct Engineer pct growth"
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    keep if role_k7 == "Engineer"
    keep companyname role_k7 year half pct_growth_role
    gen companyname_c = lower(companyname)
    gen yh = yh(year, half)
    collapse (mean) pct_growth_role, by(companyname_c yh)
    rename pct_growth_role pct_growth_eng

    tempfile GROWTH_ENG
    save `GROWTH_ENG'
restore

//---------- STEP 3: Merge Engineer growth to user panel ----------//
display _n "STEP 3: Merging Engineer growth to user panel (companyname×yh)"
merge m:1 companyname_c yh using `GROWTH_ENG'
display "Merge Engineer growth:"
tab _merge
keep if _merge == 3
drop _merge

// Drop rows where Engineer pct growth is undefined
count if missing(pct_growth_eng)
display "Dropping rows with undefined Engineer pct growth: N=" %9.0fc r(N)
drop if missing(pct_growth_eng)

//---------- STEP 4: Merge firm-time remote share ----------//
display _n "STEP 4: Merging firm-time remote share"
preserve
    use "$processed_data/firm_panel.dta", clear
    keep firm_id remote
    duplicates drop
    tempfile firm_flags
    save `firm_flags'
restore
merge m:1 firm_id using `firm_flags'
display "Merge remote flags:"
tab _merge
keep if _merge == 3
drop _merge

drop if missing(remote)
label var remote "Share on-site (remote metric)"

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

//---------- STEP 6: Estimation helper ----------//
program define run_group_irfs_engineer
    // args: if, label, outdir
    syntax [if], LABEL(string) OUTDIR(string)
    preserve
        use "$ANALYTIC", clear
        keep `if'
        count
        local N_all = r(N)
        display _n "Estimating Engineer IRFs: `label' (N=" %9.0fc `N_all' ")"
        capture mkdir "`outdir'"

        tempname hdl
        capture postclose `hdl'
        postfile `hdl' str12 rhs horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`outdir'/engineer_irf_estimates.dta", replace

        forvalues h = 0/4 {
            display "  -> Horizon `h'"
            quietly capture reghdfe F`h'_prod pct_growth_eng, absorb(user_id#firm_id yh) vce(cluster firm_id)
            display as text "     rc=`_rc'"
            if _rc == 0 {
                local N = e(N)
                local R2 = e(r2)
                local b  = _b[pct_growth_eng]
                local se = _se[pct_growth_eng]
                local t  = `b'/`se'
                local p  = 2*ttail(e(df_r), abs(`t'))
                local lo = `b' - invttail(e(df_r), 0.025)*`se'
                local hi = `b' + invttail(e(df_r), 0.025)*`se'
                post `hdl' ("Engineer") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N') (`R2')
            }
            else {
                post `hdl' ("Engineer") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
            }
        }
        postclose `hdl'

        // Export CSV
        use "`outdir'/engineer_irf_estimates.dta", clear

        // Rebase coefficients by subtracting horizon 0 within each RHS
        gen coef_rebased = coef
        gen ci_lo_rebased = ci_lo
        gen ci_hi_rebased = ci_hi

        quietly summarize coef if rhs == "Engineer" & horizon == 0, meanonly
        if r(N) {
            local base = r(mean)
            replace coef_rebased = coef - `base' if rhs == "Engineer"
            replace ci_lo_rebased = ci_lo - `base' if rhs == "Engineer"
            replace ci_hi_rebased = ci_hi - `base' if rhs == "Engineer"
            replace coef_rebased = 0 if rhs == "Engineer" & horizon == 0
            replace ci_lo_rebased = 0 if rhs == "Engineer" & horizon == 0
            replace ci_hi_rebased = 0 if rhs == "Engineer" & horizon == 0
        }

        save "`outdir'/engineer_irf_estimates.dta", replace

        export delimited using "`outdir'/engineer_irf_results.csv", replace
    restore
end

//---------- STEP 7: Run Fully Remote vs Hybrid/In-Person groups ----------//
display _n "STEP 7: Estimating by remote status"

local g1_if "remote == 1"
local g1_lab "Fully Remote (remote==1)"
local g1_dir "$results_root/remote1"

local g2_if "remote < 1"
local g2_lab "Hybrid/In-Person (remote<1)"
local g2_dir "$results_root/remote_lt1"

run_group_irfs_engineer if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_group_irfs_engineer if `g2_if', label("`g2_lab'") outdir("`g2_dir'")

//---------- SUMMARY ----------//
display _n _n "============================================================="
display "Engineer-only IRFs complete"
display "Outputs under: $results_root/"
display "  - remote1/, remote_lt1/ estimates and CSVs"
display "============================================================="

log close
