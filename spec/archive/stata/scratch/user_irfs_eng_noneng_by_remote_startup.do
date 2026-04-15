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
* user_irfs_eng_noneng_by_remote_startup.do
* Local projections of individual productivity on Engineer vs
* Non-Engineer hiring growth (two regressors), split by:
*   - Remote-first firms (remote == 1)
*   - Non-remote firms   (remote < 1)
* - Recompute growth rates from scratch by aggregating levels
*   (emp, prev) for Eng and NonEng, then (emp-prev)/prev.
* - Mirrors FE/SE used in composition IRFs; startup split removed.
*============================================================*

clear all
set more off
capture log close
log using "user_irfs_eng_noneng_by_remote.log", replace text
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

global results_root "$base_results/user_irfs_eng_vs_noneng_remote_hybrid"
capture mkdir "$results_root"

display "============================================================="
display "User IRFs: Productivity on Eng vs Non-Eng growth"
display "Split: Remote-first (remote==1) vs Remote share < 1"
display "============================================================="

//---------- STEP 1: Load user panel ----------//
display _n "STEP 1: Loading user panel"
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
assert !missing(user_id, firm_id, yh, total_contributions_q100)
display "User panel loaded: N=" %9.0fc _N

//---------- STEP 2: Build Eng/NonEng growth from scratch ----------//
display _n "STEP 2: Construct role aggregates and growth (Eng vs NonEng)"
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    // Use provided pct_growth_role for Engineer; recompute Non-Engineer from summed levels
    keep companyname role_k7 year half employee_count prev_count pct_growth_role
    gen companyname_c = lower(companyname)
    gen yh = yh(year, half)
    gen byte is_eng = (role_k7 == "Engineer")
    // Engineer growth directly from pct_growth_role
    gen pct_eng = pct_growth_role if is_eng
    // Non-Engineer levels for aggregate growth
    gen emp_noneng  = employee_count if !is_eng
    gen prev_noneng = prev_count     if !is_eng
    // Collapse to firm×time
    collapse (sum) emp_noneng prev_noneng (mean) pct_eng, by(companyname_c yh)
    // Rename engineer growth for downstream code
    rename pct_eng pct_growth_eng
    // Compute Non-Engineer growth from levels; leave undefined if prev_noneng<=0
    gen pct_growth_noneng = (emp_noneng - prev_noneng) / prev_noneng if prev_noneng > 0
    tempfile GROWTH2
    save `GROWTH2'
restore

//---------- STEP 3: Merge growths to user panel ----------//
display _n "STEP 3: Merging Eng/NonEng growths to user panel (companyname×yh)"
merge m:1 companyname_c yh using `GROWTH2'
display "Merge Eng/NonEng growths:" 
tab _merge
keep if _merge == 3
drop _merge

// Drop rows where pct growth is undefined for either RHS (econometrically strict)
count if missing(pct_growth_eng) | missing(pct_growth_noneng)
display "Dropping rows with undefined pct growth (either Eng or NonEng): N=" %9.0fc r(N)
drop if missing(pct_growth_eng) | missing(pct_growth_noneng)

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
program define run_group_irfs_2rhs
    // args: if, label, outdir
    syntax [if], LABEL(string) OUTDIR(string)
    preserve
        use "$ANALYTIC", clear
        keep `if'
        count
        local N_all = r(N)
        display _n "Estimating 2-RHS (Eng vs NonEng) IRFs: `label' (N=" %9.0fc `N_all' ")"
        capture mkdir "`outdir'"

        tempname hdl
        capture postclose `hdl'
        postfile `hdl' str12 rhs horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`outdir'/eng_noneng_irf_estimates.dta", replace

        forvalues h = 0/4 {
            display "  -> Horizon `h'"
            quietly capture reghdfe F`h'_prod pct_growth_eng pct_growth_noneng, absorb(user_id#firm_id yh) vce(cluster firm_id)
            display as text "     rc=`_rc'"
            if _rc == 0 {
                local N = e(N)
                local R2 = e(r2)
                foreach v in pct_growth_eng pct_growth_noneng {
                    local b  = _b[`v']
                    local se = _se[`v']
                    local t  = `b'/`se'
                    local p  = 2*ttail(e(df_r), abs(`t'))
                    local lo = `b' - invttail(e(df_r), 0.025)*`se'
                    local hi = `b' + invttail(e(df_r), 0.025)*`se'
                    local rname = cond("`v'"=="pct_growth_eng","Engineer","NonEngineer")
                    post `hdl' ("`rname'") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N') (`R2')
                }
            }
            else {
                foreach rname in Engineer NonEngineer {
                    post `hdl' ("`rname'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
                }
            }
        }
        postclose `hdl'

        // Export CSV
        use "`outdir'/eng_noneng_irf_estimates.dta", clear

        // Rebase coefficients by subtracting horizon 0 within each RHS
        gen coef_rebased = coef
        gen ci_lo_rebased = ci_lo
        gen ci_hi_rebased = ci_hi

        levelsof rhs, local(rhs_list)
        foreach r of local rhs_list {
            quietly summarize coef if rhs == "`r'" & horizon == 0, meanonly
            if r(N) {
                local base = r(mean)
                replace coef_rebased = coef - `base' if rhs == "`r'"
                replace ci_lo_rebased = ci_lo - `base' if rhs == "`r'"
                replace ci_hi_rebased = ci_hi - `base' if rhs == "`r'"
                replace coef_rebased = 0 if rhs == "`r'" & horizon == 0
                replace ci_lo_rebased = 0 if rhs == "`r'" & horizon == 0
                replace ci_hi_rebased = 0 if rhs == "`r'" & horizon == 0
            }
        }

        save "`outdir'/eng_noneng_irf_estimates.dta", replace

        export delimited using "`outdir'/eng_noneng_irf_results.csv", replace
    restore
end

//---------- STEP 7: Run Remote-first vs remote<1 groups ----------//
display _n "STEP 7: Estimating by remote share"

local g1_if "remote == 1"
local g1_lab "Remote-first (remote==1)"
local g1_dir "$results_root/remote1"

local g2_if "remote < 1"
local g2_lab "Remote share < 1"
local g2_dir "$results_root/remote_lt1"

run_group_irfs_2rhs if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_group_irfs_2rhs if `g2_if', label("`g2_lab'") outdir("`g2_dir'")

//---------- SUMMARY ----------//
display _n _n "============================================================="
display "2-RHS (Eng vs NonEng) IRFs complete"
display "Outputs under: $results_root/"
display "  - remote1/, remote_lt1/ estimates and CSVs"
display "============================================================="

log close
