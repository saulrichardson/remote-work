*============================================================*
* user_irfs_eng_noneng_remote_fast.do
*
* Streamlined local-projection IRFs of individual productivity
* on Engineer vs Non-Engineer hiring growth, split by:
*   - Fully remote firms (remote == 1)
*   - Firms with remote share below one (remote < 1)
*
* Inputs:
*   - $processed_data/user_panel_precovid.dta      (from build_all_user_panels.do)
*   - $processed_data/role_k7_scaling_growth.csv   (from build_role_k7_scaling_dataset.py)
*
* Outputs (per group):
*   <results_root>/<group>/eng_noneng_irf_estimates.dta
*   <results_root>/<group>/eng_noneng_irf_results.csv
*
* Results root (shared with plotting scripts):
*   results/user_irfs_eng_vs_noneng_remote_hybrid/
*
*============================================================*

clear all
set more off

****************************************************************************
* 0.  Bootstrap path/globals
****************************************************************************
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
log using "$LOG_DIR/user_irfs_eng_noneng_remote_fast.log", replace text



local panel_path  "$processed_data/user_panel_precovid.dta"
local growth_path "$processed_data/eng_noneng_growth.csv"
local results_root "$PROJECT_ROOT/results/user_irfs_eng_vs_noneng_remote_hybrid"


cap mkdir "`results_root'"

display "============================================================="
display "User IRFs (streamlined): Engineer vs Non-Engineer growth"
display "Groups: remote==1 (fully remote) vs remote<1 (hybrid/in-person)"
display "============================================================="

local out_remote "`results_root'/remote1"
local out_lt1 "`results_root'/remote_lt1"

****************************************************************************
* 1.  Prepare growth inputs (Engineer vs Non-Engineer)
****************************************************************************
tempfile growth_long
import delimited "`growth_path'", clear
keep companyname companyname_c year half pct_growth_eng pct_growth_noneng
gen yh = yh(year, half)
keep companyname_c yh pct_growth_eng pct_growth_noneng
save `growth_long'

****************************************************************************
* 2.  Load user panel and merge RHS growths
****************************************************************************
use "`panel_path'", clear
capture confirm variable remote
if _rc {
    display as error "Remote share variable not found in `panel_path'"
    exit 459
}

gen companyname_c = lower(companyname)
capture drop _merge
merge m:1 companyname_c yh using `growth_long'
keep if _merge == 3
drop _merge

drop if missing(pct_growth_eng) | missing(pct_growth_noneng)
drop if missing(remote)

* Generate half-year leads of productivity (total contributions percentile)
xtset user_id yh
forvalues h = 0/4 {
    gen F`h'_prod = F`h'.total_contributions_q100
}

tempfile analytic
save `analytic'
global ANALYTIC "`analytic'"

****************************************************************************
* 3.  Helper program: estimate IRFs for a group
****************************************************************************
program define run_remote_irf
    args cond label outdir

    preserve
        use "$ANALYTIC", clear
        keep if `cond'
        count
        local N_all = r(N)
        if `N_all' == 0 {
            display as error "No observations for condition: `cond'"
            restore
            exit
        }

        cap mkdir "`outdir'"

        tempname hdl
        capture postclose `hdl'
        postfile `hdl' str12 rhs horizon coef se tstat pval ci_lo ci_hi nobs r2 ///
            using "`outdir'/eng_noneng_irf_estimates.dta", replace

        forvalues h = 0/4 {
            quietly capture reghdfe F`h'_prod pct_growth_eng pct_growth_noneng, ///
                absorb(user_id#firm_id yh) vce(cluster firm_id)
            if _rc == 0 {
                foreach v in pct_growth_eng pct_growth_noneng {
                    local b  = _b[`v']
                    local se = _se[`v']
                    local t  = `b'/`se'
                    local p  = 2*ttail(e(df_r), abs(`t'))
                    local lo = `b' - invttail(e(df_r), 0.025)*`se'
                    local hi = `b' + invttail(e(df_r), 0.025)*`se'
                    local rhs_lab = cond("`v'"=="pct_growth_eng","Engineer","NonEngineer")
                    post `hdl' ("`rhs_lab'") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (e(N)) (e(r2))
                }
            }
            else {
                foreach rhs_lab in Engineer NonEngineer {
                    post `hdl' ("`rhs_lab'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
                }
            }
        }
        postclose `hdl'

        use "`outdir'/eng_noneng_irf_estimates.dta", clear

        gen coef_rebased = coef
        gen ci_lo_rebased = ci_lo
        gen ci_hi_rebased = ci_hi

        levelsof rhs, local(rhs_list)
        foreach r of local rhs_list {
            quietly summarize coef if rhs == "`r'" & horizon == 0, meanonly
            if r(N) {
                local base = r(mean)
                replace coef_rebased   = coef   - `base' if rhs == "`r'"
                replace ci_lo_rebased  = ci_lo  - `base' if rhs == "`r'"
                replace ci_hi_rebased  = ci_hi  - `base' if rhs == "`r'"
                replace coef_rebased   = 0 if rhs == "`r'" & horizon == 0
                replace ci_lo_rebased  = 0 if rhs == "`r'" & horizon == 0
                replace ci_hi_rebased  = 0 if rhs == "`r'" & horizon == 0
            }
        }

        save "`outdir'/eng_noneng_irf_estimates.dta", replace
        export delimited using "`outdir'/eng_noneng_irf_results.csv", replace
    restore
end

****************************************************************************
* 4.  Run groups (remote==1 vs remote<1)
****************************************************************************
run_remote_irf "remote == 1" "Remote-first (remote==1)" "`out_remote'"

run_remote_irf "remote < 1" "Remote share < 1" "`out_lt1'"

display _n "============================================================="
display "IRFs complete. Outputs in: `results_root'"
display "============================================================="

log close
