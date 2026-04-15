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
* user_irfs_technical_nontechnical_by_remote.do
* Local projections of individual productivity on Technical vs
* Non-Technical hiring growth (two regressors), split by:
*   - Remote-first firms (remote == 1)
*   - Remote share below full (remote < 1)
* Technical = Engineer + Scientist roles aggregated from levels.
* Mirrors FE/SE used in composition IRFs; startup split removed.
*============================================================*

clear all
set more off
capture log close
log using "user_irfs_technical_nontechnical_by_remote.log", replace text
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

global results_root "$base_results/user_irfs_technical_vs_nontechnical_remote"
capture mkdir "$results_root"

display "============================================================="
display "User IRFs: Productivity on Technical vs Non-Technical growth"
display "Split: Remote-first (remote==1) vs Remote share < 1"
display "============================================================="

//---------- STEP 1: Load user panel ----------//
display _n "STEP 1: Loading user panel"
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
assert !missing(user_id, firm_id, yh, total_contributions_q100)
display "User panel loaded: N=" %9.0fc _N

//---------- STEP 2: Build Technical/NonTechnical growth from levels ----------//
display _n "STEP 2: Construct role aggregates and growth (Technical vs NonTechnical)"
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    keep companyname role_k7 year half employee_count prev_count
    gen companyname_c = lower(companyname)
    gen yh = yh(year, half)
    gen byte is_technical = inlist(role_k7, "Engineer", "Scientist")

    gen emp_tech   = employee_count if is_technical
    gen prev_tech  = prev_count     if is_technical
    gen emp_non    = employee_count if !is_technical
    gen prev_non   = prev_count     if !is_technical

    collapse (sum) emp_tech prev_tech emp_non prev_non, by(companyname_c yh)

    gen pct_growth_technical = (emp_tech - prev_tech) / prev_tech if prev_tech > 0
    gen pct_growth_nontechnical = (emp_non - prev_non) / prev_non if prev_non > 0

    tempfile GROWTH_TECH
    save `GROWTH_TECH'
restore

//---------- STEP 3: Merge growths to user panel ----------//
display _n "STEP 3: Merging Technical/NonTechnical growths to user panel (companyname×yh)"
merge m:1 companyname_c yh using `GROWTH_TECH'
display "Merge Technical/NonTechnical growths:"
tab _merge
keep if _merge == 3
drop _merge

// Drop rows where pct growth is undefined for either RHS (strict sample)
count if missing(pct_growth_technical) | missing(pct_growth_nontechnical)
display "Dropping rows with undefined pct growth (either Technical or NonTechnical): N=" %9.0fc r(N)
drop if missing(pct_growth_technical) | missing(pct_growth_nontechnical)

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
program define run_group_irfs_technical
    // args: if, label, outdir
    syntax [if], LABEL(string) OUTDIR(string)
    preserve
        use "$ANALYTIC", clear
        keep `if'
        count
        local N_all = r(N)
        display _n "Estimating Technical vs NonTechnical IRFs: `label' (N=" %9.0fc `N_all' ")"
        capture mkdir "`outdir'"

        tempname hdl
        capture postclose `hdl'
        postfile `hdl' str15 rhs horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`outdir'/technical_irf_estimates.dta", replace

        forvalues h = 0/4 {
            display "  -> Horizon `h'"
            quietly capture reghdfe F`h'_prod pct_growth_technical pct_growth_nontechnical, absorb(user_id#firm_id yh) vce(cluster firm_id)
            display as text "     rc=`_rc'"
            if _rc == 0 {
                local N = e(N)
                local R2 = e(r2)
                foreach v in pct_growth_technical pct_growth_nontechnical {
                    local b  = _b[`v']
                    local se = _se[`v']
                    local t  = `b'/`se'
                    local p  = 2*ttail(e(df_r), abs(`t'))
                    local lo = `b' - invttail(e(df_r), 0.025)*`se'
                    local hi = `b' + invttail(e(df_r), 0.025)*`se'
                    local rname = cond("`v'"=="pct_growth_technical","Technical","NonTechnical")
                    post `hdl' ("`rname'") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N') (`R2')
                }
            }
            else {
                foreach rname in Technical NonTechnical {
                    post `hdl' ("`rname'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
                }
            }
        }
        postclose `hdl'

        // Export CSV
        use "`outdir'/technical_irf_estimates.dta", clear

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

        save "`outdir'/technical_irf_estimates.dta", replace

        export delimited using "`outdir'/technical_irf_results.csv", replace
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

run_group_irfs_technical if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_group_irfs_technical if `g2_if', label("`g2_lab'") outdir("`g2_dir'")

//---------- SUMMARY ----------//
display _n _n "============================================================="
display "Technical vs NonTechnical IRFs complete"
display "Outputs under: $results_root/"
display "  - remote1/, remote_lt1/ estimates and CSVs"
display "============================================================="

log close
