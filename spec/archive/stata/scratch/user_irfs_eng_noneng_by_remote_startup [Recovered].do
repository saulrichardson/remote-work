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
*   - Hybrid firms      (0 < remote < 1)
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
display "Split: Remote-first (remote==1) vs Hybrid (0<remote<1)"
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
        export delimited using "`outdir'/eng_noneng_irf_results.csv", replace
    restore
end

//---------- STEP 7: Run Remote-first vs Hybrid groups ----------//
display _n "STEP 7: Estimating by remote share"

local g1_if "remote == 1"
local g1_lab "Remote-first (remote==1)"
local g1_dir "$results_root/remote1"

local g2_if "remote > 0 & remote < 1"
local g2_lab "Hybrid (0<remote<1)"
local g2_dir "$results_root/hybrid"

run_group_irfs_2rhs if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_group_irfs_2rhs if `g2_if', label("`g2_lab'") outdir("`g2_dir'")

//---------- STEP 8: Generate IRF plots (remote-first & hybrid) ----------//
display _n "STEP 8: Creating coefficient-specific IRF plots"
tempfile COMBINED
local have_data 0

clear
foreach grp in remote1 hybrid {
    local dir "$results_root/`grp'"
    capture confirm file "`dir'/eng_noneng_irf_estimates.dta"
    if !_rc {
        use "`dir'/eng_noneng_irf_estimates.dta", clear
        gen group = "`grp'"
        gen rhs_tag = cond(rhs=="Engineer", "eng", "noneng")
        if `have_data' {
            append using `COMBINED'
        }
        save `COMBINED', replace
        local have_data 1
    }
}

local ymin_eng    = -0.2
local ymax_eng    =  0.2
local ystep_eng   =  0.1
local ymin_noneng = -0.2
local ymax_noneng =  0.2
local ystep_noneng = 0.1

if `have_data' {
    use `COMBINED', clear
    foreach coef in Engineer NonEngineer {
        preserve
            keep if rhs == "`coef'"
            local tag = cond("`coef'"=="Engineer", "eng", "noneng")
            if _N > 0 {
                quietly summarize ci_lo, meanonly
                local ymin = r(min)
                quietly summarize ci_hi, meanonly
                local ymax = r(max)
                local span = `ymax' - `ymin'
                if `span' <= 0 {
                    local span = 0.1
                }
                local pad = `span' * 0.1
                local ymin = `ymin' - `pad'
                local ymax = `ymax' + `pad'
                local ymin = round(`ymin', 0.05)
                local ymax = round(`ymax', 0.05)
                if `ymax' == `ymin' {
                    local ymax = `ymax' + 0.1
                    local ymin = `ymin' - 0.1
                }
                local ydiff = `ymax' - `ymin'
                if `ydiff' <= 0 {
                    local ydiff = 0.4
                }
                local ystep = round(`ydiff'/4, 0.05)
                if `ystep' <= 0 {
                    local ystep = 0.05
                }
            }
            else {
                local ymin = -0.2
                local ymax = 0.2
                local ystep = 0.1
            }
            local ymin_`tag' = `ymin'
            local ymax_`tag' = `ymax'
            local ystep_`tag' = `ystep'
        restore
    }
}

foreach fname in plot_remote.png plot_hybrid.png plot_engineer.png plot_nonengineer.png plot_combined.png {
    capture erase "$results_root/`fname'"
}

foreach grp in remote1 hybrid {
    local dir "$results_root/`grp'"
    local grp_title = cond("`grp'"=="remote1", "Remote-first firms", "Hybrid firms")
    local grp_stub  = cond("`grp'"=="remote1", "plot_remote", "plot_hybrid")
    capture use "`dir'/eng_noneng_irf_estimates.dta", clear
    if !_rc {
        foreach coef in Engineer NonEngineer {
            preserve
                keep if rhs == "`coef'"
                if _N == 0 {
                    restore
                    continue
                }
                local coef_tag = cond("`coef'"=="Engineer", "eng", "noneng")
                local coef_title = cond("`coef'"=="Engineer", "Engineer growth", "Non-Engineer growth")
                local fname = "`grp_stub'_`coef_tag'.png"
                twoway ///
                    (rcap ci_lo ci_hi horizon, lcolor(gs10) lwidth(medthin)) ///
                    (connected coef horizon, lcolor(navy) mcolor(navy) msymbol(circle) lwidth(medthick)), ///
                    yline(0, lpattern(dash) lcolor(gs8)) ///
                    ylabel(`ymin_`coef_tag''(`ystep_`coef_tag'')`ymax_`coef_tag'', format(%5.2f)) ///
                    xlabel(0(1)4) ///
                    xtitle("Horizon (6-month periods)") ///
                    ytitle("Productivity IRF") ///
                    title("`grp_title' — `coef_title'") legend(off) ///
                    graphregion(color(white)) plotregion(color(white))
                graph export "$results_root/`fname'", replace width(900) height(650)
            restore
        }
    }
}


//---------- SUMMARY ----------//
display _n _n "============================================================="
display "2-RHS (Eng vs NonEng) IRFs complete"
display "Outputs under: $results_root/"
display "  - remote1/, hybrid/ estimates and CSVs"
display "  - plot_remote_eng.png, plot_remote_noneng.png"
display "  - plot_hybrid_eng.png, plot_hybrid_noneng.png"
display "============================================================="

log close
